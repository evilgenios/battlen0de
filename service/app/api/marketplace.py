"""Marketplace routes. Authentication, CSRF, ownership and release gates live on the server."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.db.marketplace import (
    MarketplaceAuditEvent, MarketplaceConversation, MarketplaceFavorite, MarketplaceListing,
    MarketplaceMessage, MarketplaceNotification, MarketplaceProfile, MarketplaceReport, MarketplaceStore,
)
from app.deps import enforce_product_rate_limit, get_current_user, get_repository, require_admin
from app.schemas.marketplace import DecisionInput, ListingEdit, ListingInput, MessageInput, PermissionsInput, ProfileInput, ReportInput, VersionInput
from app.services.marketplace import capabilities, require_live, require_owner, require_staff, require_unrestricted, require_version

router = APIRouter(prefix='/marketplace', tags=['marketplace'])
private = APIRouter(dependencies=[Depends(enforce_product_rate_limit)])


def store(request: Request) -> MarketplaceStore:
    result = getattr(request.app.state, 'marketplace_store', None)
    if result is None:
        raise HTTPException(503, 'Marketplace storage is not available. Apply the marketplace migration and restart the service.')
    return result


def listing_or_404(session, listing_id, *, lock=False):
    query = select(MarketplaceListing).where(MarketplaceListing.id == listing_id)
    row = session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(404, 'listing not found')
    return row


def serialize(session, row, *, private=False):
    return MarketplaceStore.listing(row, session.get(MarketplaceProfile, row.seller_id), private=private)


def visible_listing(session, listing_id):
    require_live()
    row = listing_or_404(session, listing_id)
    profile = session.get(MarketplaceProfile, row.seller_id)
    if row.status != 'active' or profile is None or profile.restricted or not profile.seller_enabled:
        raise HTTPException(404, 'listing not found')
    return row


@router.get('/config')
def config():
    return capabilities()


@router.get('/listings')
def listings(
    database: MarketplaceStore = Depends(store), q: str = Query('', max_length=100),
    server: int | None = Query(None, ge=1, le=10000), min_strength: int = Query(0, ge=0),
    min_collector: int = Query(0, ge=0), min_airspace: int = Query(0, ge=0),
    max_price: int | None = Query(None, ge=100), composition: str = Query('', max_length=24),
    min_vip: int = Query(0, ge=0), min_commander: int = Query(0, ge=0), min_research: int = Query(0, ge=0, le=100),
    sort: str = Query('newest', pattern='^(newest|price_asc|price_desc|strength)$'),
    offset: int = Query(0, ge=0, le=10000), limit: int = Query(24, ge=1, le=60),
):
    if not capabilities()['public_listings_enabled']:
        return {'items': [], 'total': 0, 'mode': 'preview'}
    with database.sessions() as session:
        query = select(MarketplaceListing).join(MarketplaceProfile, MarketplaceProfile.user_id == MarketplaceListing.seller_id).where(
            MarketplaceListing.status == 'active', MarketplaceProfile.restricted.is_(False), MarketplaceProfile.seller_enabled.is_(True),
            MarketplaceListing.strength >= min_strength, MarketplaceListing.collector_level >= min_collector, MarketplaceListing.airspace >= min_airspace,
            MarketplaceListing.vip >= min_vip, MarketplaceListing.commander_level >= min_commander, MarketplaceListing.research >= min_research,
        )
        if q:
            # autoescape prevents user wildcards from turning a search into a full-table scan.
            query = query.where(or_(MarketplaceListing.title.icontains(q, autoescape=True), MarketplaceListing.commander_name.icontains(q, autoescape=True)))
        if server is not None:
            query = query.where(MarketplaceListing.server == server)
        if max_price is not None:
            query = query.where(MarketplaceListing.price_cents <= max_price)
        if composition:
            query = query.where(MarketplaceListing.composition == composition)
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        order = {'newest': MarketplaceListing.created_at.desc(), 'price_asc': MarketplaceListing.price_cents.asc(),
                 'price_desc': MarketplaceListing.price_cents.desc(), 'strength': MarketplaceListing.strength.desc()}[sort]
        rows = session.scalars(query.order_by(order, MarketplaceListing.id).offset(offset).limit(limit))
        return {'items': [serialize(session, row) for row in rows], 'total': total, 'mode': 'live'}


@router.get('/listings/{listing_id}')
def listing(listing_id: uuid.UUID, database: MarketplaceStore = Depends(store)):
    with database.sessions() as session:
        return serialize(session, visible_listing(session, listing_id))


@private.get('/me/dashboard')
def dashboard(user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        profile = database.profile(session, user.id)
        rows = list(session.scalars(select(MarketplaceListing).where(MarketplaceListing.seller_id == user.id).order_by(MarketplaceListing.updated_at.desc()).limit(100)))
        return {
            'profile': {'display_name': profile.display_name, 'seller_enabled': profile.seller_enabled or user.is_admin,
                        'staff_role': 'owner' if user.is_admin else profile.staff_role, 'restricted': profile.restricted},
            'listings': [serialize(session, row, private=True) for row in rows],
            'counts': {'active': sum(row.status == 'active' for row in rows), 'pending_review': sum(row.status == 'pending_review' for row in rows),
                       'draft': sum(row.status == 'draft' for row in rows),
                       'favorites': session.scalar(select(func.count()).select_from(MarketplaceFavorite).where(MarketplaceFavorite.user_id == user.id)),
                       'conversations': session.scalar(select(func.count()).select_from(MarketplaceConversation).where(or_(MarketplaceConversation.buyer_id == user.id, MarketplaceConversation.seller_id == user.id)))},
            'notifications': [{'id': n.id, 'text': n.text, 'created_at': n.created_at} for n in session.scalars(
                select(MarketplaceNotification).where(MarketplaceNotification.user_id == user.id).order_by(MarketplaceNotification.created_at.desc()).limit(20))],
        }


@private.patch('/me/profile')
def edit_profile(body: ProfileInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        profile = database.profile(session, user.id)
        profile.display_name = body.display_name
        database.audit(session, user.id, None, 'profile_updated')
    return {'ok': True}


@private.post('/listings', status_code=201)
def create_listing(body: ListingInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    try:
        with database.sessions.begin() as session:
            require_unrestricted(session, user)
            database.profile(session, user.id)
            count = session.scalar(select(func.count()).select_from(MarketplaceListing).where(MarketplaceListing.seller_id == user.id))
            if count >= 100:
                raise HTTPException(409, 'listing limit reached')
            row = MarketplaceListing(seller_id=user.id, **body.model_dump())
            session.add(row)
            session.flush()
            database.audit(session, user.id, row.id, 'listing_created')
            return serialize(session, row, private=True)
    except IntegrityError:
        raise HTTPException(409, 'A listing already exists for this commander and server.')


@private.get('/me/listings/{listing_id}')
def own_listing(listing_id: uuid.UUID, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions() as session:
        row = listing_or_404(session, listing_id)
        require_owner(row, user)
        return serialize(session, row, private=True)


@private.patch('/listings/{listing_id}')
def edit_listing(listing_id: uuid.UUID, body: ListingEdit, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    try:
        with database.sessions.begin() as session:
            require_unrestricted(session, user)
            row = listing_or_404(session, listing_id, lock=True)
            require_owner(row, user)
            require_version(row, body.version)
            if row.status not in ('draft', 'paused'):
                raise HTTPException(409, 'Pause the listing or wait for review before editing.')
            for key, value in body.model_dump(exclude={'version'}).items():
                setattr(row, key, value)
            row.status, row.stats_reviewed, row.control_demonstrated = 'draft', False, False
            row.review_note = ''
            row.version += 1
            database.audit(session, user.id, row.id, 'listing_edited', version=row.version)
            session.flush()
            return serialize(session, row, private=True)
    except IntegrityError:
        raise HTTPException(409, 'A listing already exists for this commander and server.')


@private.post('/listings/{listing_id}/{action}')
def transition(listing_id: uuid.UUID, action: str, body: VersionInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        row = listing_or_404(session, listing_id, lock=True)
        require_owner(row, user)
        require_version(row, body.version)
        allowed = {'submit': (('draft', 'paused'), 'pending_review'), 'pause': (('active',), 'paused'),
                   'withdraw': (('draft', 'pending_review', 'active', 'paused'), 'removed')}
        if action not in allowed:
            raise HTTPException(404, 'action not found')
        sources, target = allowed[action]
        if row.status not in sources:
            raise HTTPException(409, 'This transition is not available for the current listing status.')
        if action == 'submit':
            profile = database.profile(session, user.id)
            if not (profile.seller_enabled or user.is_admin):
                raise HTTPException(403, 'Seller approval is required before submitting a listing.')
            if len(row.evidence.strip()) < 20:
                raise HTTPException(422, 'Add supporting evidence notes before submitting for review.')
        row.status = target
        row.version += 1
        database.audit(session, user.id, row.id, f'listing_{action}', version=row.version)
        session.flush()
        return serialize(session, row, private=True)


@private.get('/me/favorites')
def favorites(user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    if not capabilities()['public_listings_enabled']:
        return []
    with database.sessions() as session:
        rows = session.scalars(select(MarketplaceListing).join(MarketplaceFavorite, MarketplaceFavorite.listing_id == MarketplaceListing.id)
            .join(MarketplaceProfile, MarketplaceProfile.user_id == MarketplaceListing.seller_id)
            .where(MarketplaceFavorite.user_id == user.id, MarketplaceListing.status == 'active', MarketplaceProfile.restricted.is_(False), MarketplaceProfile.seller_enabled.is_(True)))
        return [serialize(session, row) for row in rows]


@private.post('/favorites/{listing_id}')
def favorite(listing_id: uuid.UUID, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        visible_listing(session, listing_id)
        # Lock the profile to serialize repeated favorite toggles by the same user.
        database.profile(session, user.id)
        session.scalar(select(MarketplaceProfile).where(MarketplaceProfile.user_id == user.id).with_for_update())
        existing = session.get(MarketplaceFavorite, (user.id, listing_id))
        if existing:
            session.delete(existing)
        else:
            session.add(MarketplaceFavorite(user_id=user.id, listing_id=listing_id))
        return {'saved': existing is None}


@private.post('/reports/{listing_id}', status_code=201)
def report(listing_id: uuid.UUID, body: ReportInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        visible_listing(session, listing_id)
        session.add(MarketplaceReport(listing_id=listing_id, reporter_id=user.id, reason=body.reason))
        database.audit(session, user.id, listing_id, 'listing_reported')
    return {'ok': True}


@private.get('/conversations')
def conversations(user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions() as session:
        rows = session.scalars(select(MarketplaceConversation).where(or_(MarketplaceConversation.buyer_id == user.id, MarketplaceConversation.seller_id == user.id)).order_by(MarketplaceConversation.created_at.desc()).limit(100))
        return [{'id': row.id, 'listing_id': row.listing_id, 'title': listing_or_404(session, row.listing_id).title} for row in rows]


@private.post('/conversations/{listing_id}', status_code=201)
def start_conversation(listing_id: uuid.UUID, body: MessageInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        row = visible_listing(session, listing_id)
        if row.seller_id == user.id:
            raise HTTPException(409, 'You cannot send an inquiry to yourself.')
        # Listing lock serializes duplicate thread creation.
        listing_or_404(session, listing_id, lock=True)
        thread = session.scalar(select(MarketplaceConversation).where(MarketplaceConversation.listing_id == listing_id, MarketplaceConversation.buyer_id == user.id))
        if thread is None:
            thread = MarketplaceConversation(listing_id=listing_id, buyer_id=user.id, seller_id=row.seller_id)
            session.add(thread)
            session.flush()
        session.add(MarketplaceMessage(conversation_id=thread.id, sender_id=user.id, body=body.body))
        database.notify(session, row.seller_id, f'New inquiry about {row.title}')
        return {'id': thread.id}


def participant(session, conversation_id, user):
    thread = session.get(MarketplaceConversation, conversation_id)
    if thread is None or user.id not in (thread.buyer_id, thread.seller_id):
        raise HTTPException(404, 'conversation not found')
    return thread


@private.get('/conversations/{conversation_id}/messages')
def messages(conversation_id: uuid.UUID, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions() as session:
        participant(session, conversation_id, user)
        rows = session.scalars(select(MarketplaceMessage).where(MarketplaceMessage.conversation_id == conversation_id).order_by(MarketplaceMessage.created_at.desc(), MarketplaceMessage.id.desc()).limit(200))
        return list(reversed([{'id': m.id, 'body': m.body, 'mine': m.sender_id == user.id, 'created_at': m.created_at} for m in rows]))


@private.post('/conversations/{conversation_id}/messages', status_code=201)
def send_message(conversation_id: uuid.UUID, body: MessageInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    require_live()
    with database.sessions.begin() as session:
        require_unrestricted(session, user)
        thread = participant(session, conversation_id, user)
        target = thread.seller_id if user.id == thread.buyer_id else thread.buyer_id
        target_profile = session.get(MarketplaceProfile, target)
        if target_profile and target_profile.restricted:
            raise HTTPException(409, 'This conversation is unavailable.')
        session.add(MarketplaceMessage(conversation_id=thread.id, sender_id=user.id, body=body.body))
        database.notify(session, target, 'New marketplace message')
    return {'ok': True}


@private.get('/admin/reviews')
def reviews(user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions() as session:
        require_staff(session, user)
        rows = session.scalars(select(MarketplaceListing).where(MarketplaceListing.status == 'pending_review').order_by(MarketplaceListing.created_at).limit(100))
        reports = session.scalars(select(MarketplaceReport).where(MarketplaceReport.resolved.is_(False)).order_by(MarketplaceReport.created_at).limit(100))
        events = session.scalars(select(MarketplaceAuditEvent).order_by(MarketplaceAuditEvent.created_at.desc()).limit(30))
        return {'listings': [serialize(session, row, private=True) for row in rows],
                'reports': [{'id': r.id, 'listing_id': r.listing_id, 'title': listing_or_404(session, r.listing_id).title, 'version': listing_or_404(session, r.listing_id).version, 'reason': r.reason} for r in reports],
                'events': [{'id': e.id, 'action': e.action, 'created_at': e.created_at} for e in events]}


@private.post('/admin/listings/{listing_id}/decision')
def decision(listing_id: uuid.UUID, body: DecisionInput, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_staff(session, user)
        row = listing_or_404(session, listing_id, lock=True)
        if row.seller_id == user.id:
            raise HTTPException(403, 'A different reviewer must review your listing.')
        require_version(row, body.version)
        if body.decision == 'remove':
            if row.status == 'removed':
                raise HTTPException(409, 'Listing has already been removed.')
            target = 'removed'
        else:
            if row.status != 'pending_review':
                raise HTTPException(409, 'Listing is not awaiting review.')
            target = 'active' if body.decision == 'approve' else 'draft'
        row.status, row.review_note = target, body.note
        row.stats_reviewed = body.stats_reviewed if body.decision == 'approve' else False
        row.control_demonstrated = body.control_demonstrated if body.decision == 'approve' else False
        row.version += 1
        database.audit(session, user.id, row.id, f'review_{body.decision}', note=body.note,
                       stats_reviewed=row.stats_reviewed, control_demonstrated=row.control_demonstrated, version=row.version)
        database.notify(session, row.seller_id, f'{row.title}: {body.decision}. {body.note}')
        session.flush()
        return serialize(session, row, private=True)


@private.post('/admin/reports/{report_id}/resolve')
def resolve_report(report_id: uuid.UUID, user=Depends(get_current_user), database: MarketplaceStore = Depends(store)):
    with database.sessions.begin() as session:
        require_staff(session, user)
        row = session.get(MarketplaceReport, report_id)
        if row is None:
            raise HTTPException(404, 'report not found')
        row.resolved = True
        database.audit(session, user.id, row.listing_id, 'report_resolved', report_id=str(row.id))
    return {'ok': True}


@private.patch('/admin/profiles/{user_id}')
def permissions(user_id: uuid.UUID, body: PermissionsInput, user=Depends(require_admin), repo=Depends(get_repository), database: MarketplaceStore = Depends(store)):
    if repo.get_user_by_id(user_id) is None:
        raise HTTPException(404, 'user not found')
    with database.sessions.begin() as session:
        profile = database.profile(session, user_id)
        for key, value in body.model_dump().items():
            setattr(profile, key, value)
        database.audit(session, user.id, None, 'permissions_updated', user_id=str(user_id), **body.model_dump())
    return {'ok': True}


router.include_router(private)
