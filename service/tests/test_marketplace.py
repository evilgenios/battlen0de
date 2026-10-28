"""Marketplace HTTP policies against real SQL storage, with synthetic website identities.

SQLite exercises persistence/constraints here. PostgreSQL locking and migration
integration additionally require TEST_DATABASE_URL; these tests don't claim that coverage.
"""
import uuid

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.marketplace import MARKETPLACE_TABLES, MarketplaceAuditEvent, MarketplaceListing, MarketplaceProfile, MarketplaceStore
from app.deps import AuthenticatedUser, get_current_user

INPUT = dict(title='QA ground commander', description='Synthetic test commander with a developed ground roster.',
    commander_name='Test Commander', commander_id='123456', server=32, strength=822000000,
    commander_level=80, collector_level=68, airspace=1900, vip=18, composition='ground',
    research=92, price_cents=145000, currency='USD', evidence='Synthetic evidence notes for the review workflow.')
FLAGS = ('MARKETPLACE_PUBLIC_ENABLED', 'MARKETPLACE_PUBLISHER_APPROVED', 'MARKETPLACE_LEGAL_APPROVED', 'MARKETPLACE_PROVIDER_APPROVED')


@pytest.fixture
def market(api_client, fake_repo, monkeypatch):
    for flag in FLAGS:
        monkeypatch.delenv(flag, raising=False)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        connection.execute(text('CREATE TABLE users (id CHAR(32) PRIMARY KEY)'))
    for table in MARKETPLACE_TABLES:
        table.create(engine)
    database = MarketplaceStore(sessionmaker(engine))
    api_client.app.state.marketplace_store = database
    current = {}

    def actor(name, role='member', seller=False, staff_role='user'):
        record = fake_repo.get_or_create_user(f'{name}@example.test')
        with engine.begin() as connection:
            connection.execute(text('INSERT OR IGNORE INTO users (id) VALUES (:id)'), {'id': record.id.hex})
        current['user'] = AuthenticatedUser(id=record.id, email=record.email, role=role)
        with database.sessions.begin() as session:
            profile = database.profile(session, record.id)
            profile.seller_enabled = seller
            profile.staff_role = staff_role
        return current['user']

    actor('seller', seller=True)
    api_client.app.dependency_overrides[get_current_user] = lambda: current['user']
    yield api_client, database, actor
    api_client.app.dependency_overrides.clear()
    engine.dispose()


def create(client, **changes):
    response = client.post('/marketplace/listings', json={**INPUT, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def activate(client, actor):
    actor('seller', seller=True)
    row = create(client)
    assert client.post(f"/marketplace/listings/{row['id']}/submit", json={'version': 1}).status_code == 200
    actor('reviewer', staff_role='moderator')
    response = client.post(f"/marketplace/admin/listings/{row['id']}/decision", json={'version': 2, 'decision': 'approve', 'note': 'Statistics evidence reviewed.', 'stats_reviewed': True})
    assert response.status_code == 200, response.text
    return response.json()


def enable(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, 'true')


def test_release_gates_are_explicit_and_payments_always_disabled(market, monkeypatch):
    client, _, _ = market
    for flag in FLAGS[:-1]:
        monkeypatch.setenv(flag, 'true')
    assert client.get('/marketplace/config').json()['mode'] == 'preview'
    monkeypatch.setenv(FLAGS[-1], 'true')
    config = client.get('/marketplace/config').json()
    assert config['public_listings_enabled'] is True
    assert config['payments_enabled'] is config['offers_enabled'] is config['uploads_enabled'] is config['transfers_enabled'] is False


def test_anonymous_cannot_access_private_workspace_or_write(market, monkeypatch):
    client, _, _ = market
    client.app.dependency_overrides.clear()
    monkeypatch.setenv('AUTH_MODE', 'session')
    assert client.get('/marketplace/config').status_code == 200
    assert client.get('/marketplace/listings').json()['items'] == []
    assert client.get('/marketplace/me/dashboard').status_code == 401
    assert client.post('/marketplace/listings', json=INPUT).status_code == 401
    assert client.get('/marketplace/admin/reviews').status_code == 401


def test_mutations_use_existing_csrf_boundary(market, monkeypatch):
    client, _, actor = market
    user = actor('session-user')
    client.app.dependency_overrides.clear()
    monkeypatch.setenv('AUTH_MODE', 'session')
    session = client.app.state.dashboard_sessions.create(user_id=user.id, email=user.email, role='member')
    client.cookies.set('dashboard_session', session.session_id)
    client.cookies.set('dashboard_csrf', session.csrf_token)
    assert client.post('/marketplace/listings', json=INPUT).status_code == 403
    assert client.post('/marketplace/listings', json=INPUT, headers={'x-csrf-token': session.csrf_token}).status_code == 201


def test_draft_is_durable_private_and_does_not_link_a_game_account(market):
    client, database, actor = market
    row = create(client)
    assert client.get(f"/marketplace/me/listings/{row['id']}").json()['title'] == INPUT['title']
    assert client.get('/marketplace/listings').json()['items'] == []
    assert client.get('/accounts').json() == []
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketplaceListing)) == 1
        assert session.scalar(select(func.count()).select_from(MarketplaceAuditEvent)) == 1
    actor('other', role='admin')
    assert client.get(f"/marketplace/me/listings/{row['id']}").status_code == 404
    assert client.patch(f"/marketplace/listings/{row['id']}", json={**INPUT, 'version': 1}).status_code == 404


def test_writes_reject_credentials_and_client_supplied_approval(market):
    client, _, _ = market
    for extra in ({'app_token': 'test-secret'}, {'status': 'active'}, {'stats_reviewed': True}, {'seller_id': str(uuid.uuid4())}):
        response = client.post('/marketplace/listings', json={**INPUT, **extra})
        assert response.status_code == 422
        assert 'test-secret' not in response.text


def test_duplicate_commander_rejected_even_for_another_seller(market):
    client, _, actor = market
    create(client)
    actor('different-seller')
    assert client.post('/marketplace/listings', json=INPUT).status_code == 409


def test_seller_approval_required_and_restrictions_enforced(market):
    client, database, actor = market
    user = actor('unapproved')
    row = create(client)
    assert client.post(f"/marketplace/listings/{row['id']}/submit", json={'version': 1}).status_code == 403
    with database.sessions.begin() as session:
        session.get(MarketplaceProfile, user.id).restricted = True
    assert client.patch(f"/marketplace/listings/{row['id']}", json={**INPUT, 'version': 1}).status_code == 403


def test_stale_edits_cannot_overwrite_or_skip_review(market):
    client, _, _ = market
    row = create(client)
    url = f"/marketplace/listings/{row['id']}"
    assert client.patch(url, json={**INPUT, 'title': 'Updated commander draft', 'version': 1}).json()['version'] == 2
    assert client.patch(url, json={**INPUT, 'version': 1}).status_code == 409
    assert client.post(url + '/submit', json={'version': 2}).status_code == 200
    assert client.patch(url, json={**INPUT, 'version': 3}).status_code == 409


def test_independent_review_audited_and_still_hidden_in_preview(market):
    client, database, actor = market
    row = activate(client, actor)
    assert row['status'] == 'active' and row['stats_reviewed'] is True and row['control_demonstrated'] is False
    assert client.get('/marketplace/listings').json()['items'] == []
    assert client.get(f"/marketplace/listings/{row['id']}").status_code == 409
    actor('seller', seller=True)
    assert client.get('/marketplace/me/dashboard').json()['notifications']
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketplaceAuditEvent)) == 3


def test_review_cannot_be_self_approved_or_replayed(market):
    client, _, actor = market
    actor('seller', role='admin', seller=True)
    row = create(client)
    client.post(f"/marketplace/listings/{row['id']}/submit", json={'version': 1})
    url = f"/marketplace/admin/listings/{row['id']}/decision"
    body = {'version': 2, 'decision': 'approve', 'note': 'Review notes.'}
    assert client.post(url, json=body).status_code == 403
    actor('other-moderator', staff_role='moderator')
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json=body).status_code == 409


def test_public_response_filters_stats_and_redacts_private_evidence(market, monkeypatch):
    client, _, actor = market
    row = activate(client, actor)
    enable(monkeypatch)
    public = client.get('/marketplace/listings?server=32&min_airspace=1900').json()
    assert public['total'] == 1
    assert not {'commander_id', 'evidence', 'review_note', 'seller_id'} & public['items'][0].keys()
    assert client.get('/marketplace/listings?server=41').json()['total'] == 0
    assert client.get('/marketplace/listings?min_strength=900000000').json()['total'] == 0
    assert client.get('/marketplace/listings?min_vip=19').json()['total'] == 0
    assert client.get('/marketplace/listings?max_price=100000').json()['total'] == 0
    assert client.get(f"/marketplace/listings/{row['id']}").status_code == 200


def test_conversations_are_participant_only_and_preview_blocks_new_messages(market, monkeypatch):
    client, _, actor = market
    row = activate(client, actor)
    enable(monkeypatch)
    actor('buyer')
    response = client.post(f"/marketplace/conversations/{row['id']}", json={'body': 'Are the statistics current?'})
    assert response.status_code == 201
    thread = response.json()['id']
    assert client.post(f"/marketplace/conversations/{row['id']}", json={'body': 'A follow-up.'}).json()['id'] == thread
    actor('outsider', role='admin')
    assert client.get(f'/marketplace/conversations/{thread}/messages').status_code == 404
    assert client.post(f'/marketplace/conversations/{thread}/messages', json={'body': 'Intrusion.'}).status_code == 404
    actor('seller', seller=True)
    assert len(client.get(f'/marketplace/conversations/{thread}/messages').json()) == 2
    assert client.post(f'/marketplace/conversations/{thread}/messages', json={'body': 'Yes, these are current.'}).status_code == 201
    monkeypatch.setenv(FLAGS[0], 'false')
    assert client.post(f'/marketplace/conversations/{thread}/messages', json={'body': 'Blocked.'}).status_code == 409
    assert client.get(f'/marketplace/conversations/{thread}/messages').status_code == 200


def test_favorites_reports_and_restricted_sellers_do_not_leak(market, monkeypatch):
    client, database, actor = market
    row = activate(client, actor)
    enable(monkeypatch)
    actor('buyer')
    assert client.post(f"/marketplace/favorites/{row['id']}").json()['saved'] is True
    assert len(client.get('/marketplace/me/favorites').json()) == 1
    assert client.post(f"/marketplace/reports/{row['id']}", json={'reason': 'Synthetic duplicate statistics report.'}).status_code == 201
    actor('reviewer', staff_role='moderator')
    reports = client.get('/marketplace/admin/reviews').json()['reports']
    assert len(reports) == 1
    assert client.post(f"/marketplace/admin/reports/{reports[0]['id']}/resolve").status_code == 200
    seller = actor('seller', seller=True)
    with database.sessions.begin() as session:
        session.get(MarketplaceProfile, seller.id).restricted = True
    actor('buyer')
    assert client.get('/marketplace/me/favorites').json() == []
    assert client.get('/marketplace/listings').json()['total'] == 0
    assert client.get(f"/marketplace/listings/{row['id']}").status_code == 404


def test_moderator_cannot_change_permissions_or_operational_roles(market):
    client, _, actor = market
    user = actor('plain-user')
    assert client.get('/marketplace/admin/reviews').status_code == 403
    actor('moderator', staff_role='moderator')
    assert client.get('/marketplace/admin/reviews').status_code == 200
    assert client.patch(f'/marketplace/admin/profiles/{user.id}', json={'seller_enabled': True, 'staff_role': 'owner'}).status_code == 403
    actor('platform-admin', role='admin')
    assert client.patch(f'/marketplace/admin/profiles/{user.id}', json={'seller_enabled': True, 'staff_role': 'moderator'}).status_code == 200


def test_pausing_and_editing_requires_fresh_verification(market):
    client, _, actor = market
    row = activate(client, actor)
    actor('seller', seller=True)
    paused = client.post(f"/marketplace/listings/{row['id']}/pause", json={'version': row['version']}).json()
    changed = client.patch(f"/marketplace/listings/{row['id']}", json={**INPUT, 'version': paused['version']}).json()
    assert changed['status'] == 'draft'
    assert changed['stats_reviewed'] is changed['control_demonstrated'] is False
