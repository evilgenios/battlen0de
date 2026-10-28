"""Owner, atomic claims, TTL and resend bookkeeping. No external I/O."""
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.core.link_challenge_store import ChallengeError, LinkChallengeStore
from app.core.warpath.credentials import WarpathCredentials

OWNER, OTHER = uuid.uuid4(), uuid.uuid4()


def ready(store):
    p = store.begin_send(owner_user_id=OWNER, email='player@example.test',
                         vehicle=WarpathCredentials(account_id='synthetic', app_uid='123', app_token='fake', device_id='synthetic'))
    store.finish_send(p.challenge_id, OWNER, p.link_session)
    return p


def test_roundtrip_and_ttl():
    store = LinkChallengeStore()
    p = ready(store)
    assert store.get(p.challenge_id, OWNER) is p
    p.created_at -= store.ttl_seconds + 1
    assert store.get(p.challenge_id, OWNER) is None


def test_every_challenge_operation_requires_owner():
    store = LinkChallengeStore(resend_cooldown_seconds=0)
    p = ready(store)
    assert store.get(p.challenge_id, OTHER) is None
    for action in [lambda: store.claim_verification(p.challenge_id, OTHER),
                   lambda: store.discard(p.challenge_id, OTHER),
                   lambda: store.finish_verification(p.challenge_id, OTHER, success=True),
                   lambda: store.finish_send(p.challenge_id, OTHER, p.link_session),
                   lambda: store.begin_send(owner_user_id=OTHER, email=p.email, vehicle=p.vehicle, challenge_id=p.challenge_id)]:
        with pytest.raises(ChallengeError) as error:
            action()
        assert error.value.status == 410
    assert p.attempts == 0
    assert store.get(p.challenge_id, OWNER) is p


def test_attempt_cap_consumes_challenge():
    store = LinkChallengeStore(max_attempts=2)
    p = ready(store)
    for i in range(2):
        assert store.claim_verification(p.challenge_id, OWNER).attempts == i + 1
        store.finish_verification(p.challenge_id, OWNER, success=False)
    with pytest.raises(ChallengeError) as error:
        store.claim_verification(p.challenge_id, OWNER)
    assert error.value.status == 429
    assert store.get(p.challenge_id, OWNER) is None


def test_only_one_concurrent_verification_claim_and_busy_resend_delete_denied():
    store = LinkChallengeStore(resend_cooldown_seconds=0)
    p = ready(store)
    def claim(_):
        try:
            return store.claim_verification(p.challenge_id, OWNER)
        except ChallengeError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(8)))
    assert results.count(409) == 7
    assert p.attempts == 1
    for action in [lambda: store.discard(p.challenge_id, OWNER),
                   lambda: store.begin_send(owner_user_id=OWNER, email=p.email, vehicle=p.vehicle)]:
        with pytest.raises(ChallengeError) as error:
            action()
        assert error.value.status == 409
    p.created_at -= store.ttl_seconds + 1
    assert store.get(p.challenge_id, OWNER) is p
    store.finish_verification(p.challenge_id, OWNER, success=True)
    assert store.get(p.challenge_id, OWNER) is None


def test_send_claim_blocks_duplicate_request_and_verification():
    store = LinkChallengeStore(resend_cooldown_seconds=0)
    p = ready(store)
    store.claim_verification(p.challenge_id, OWNER)
    store.finish_verification(p.challenge_id, OWNER, success=False)
    resent = store.begin_send(owner_user_id=OWNER, email=p.email, vehicle=p.vehicle)
    assert resent.challenge_id == p.challenge_id
    with pytest.raises(ChallengeError):
        store.claim_verification(p.challenge_id, OWNER)
    with pytest.raises(ChallengeError):
        store.begin_send(owner_user_id=OWNER, email=p.email, vehicle=p.vehicle)
    store.finish_send(p.challenge_id, OWNER, p.link_session)
    assert p.attempts == 0
    store.discard(p.challenge_id, OWNER)
    assert store.get(p.challenge_id, OWNER) is None


def test_same_email_has_independent_owner_challenges():
    store = LinkChallengeStore()
    p = ready(store)
    other = store.begin_send(owner_user_id=OTHER, email=p.email, vehicle=p.vehicle)
    assert other.challenge_id != p.challenge_id
    assert other.link_session != p.link_session


def test_failed_new_send_removed_and_failed_resend_preserves_attempts():
    store = LinkChallengeStore(resend_cooldown_seconds=0)
    p = ready(store)
    store.claim_verification(p.challenge_id, OWNER)
    store.finish_verification(p.challenge_id, OWNER, success=False)
    store.begin_send(owner_user_id=OWNER, email=p.email, vehicle=p.vehicle)
    store.finish_send(p.challenge_id, OWNER, None)
    assert p.attempts == 1
    other = store.begin_send(owner_user_id=OTHER, email=p.email, vehicle=p.vehicle)
    store.finish_send(other.challenge_id, OTHER, None)
    assert store.get(other.challenge_id, OTHER) is None
