"""Release gates and resource policies independent of Warpath operations."""
import os
from fastapi import HTTPException
from app.db.marketplace import MarketplaceProfile


def capabilities():
    # Three explicit server-side attestations. Payments/transfers have no implementation or override.
    approved = all(os.environ.get(key, '').strip().lower() == 'true' for key in (
        'MARKETPLACE_PUBLISHER_APPROVED', 'MARKETPLACE_LEGAL_APPROVED', 'MARKETPLACE_PROVIDER_APPROVED',
    ))
    public = approved and os.environ.get('MARKETPLACE_PUBLIC_ENABLED', '').strip().lower() == 'true'
    return {'mode': 'live' if public else 'preview', 'public_listings_enabled': public,
            'messaging_enabled': public, 'offers_enabled': False, 'payments_enabled': False,
            'uploads_enabled': False, 'transfers_enabled': False}


def staff(session, user):
    profile = session.get(MarketplaceProfile, user.id)
    return user.is_admin or bool(profile and not profile.restricted and profile.staff_role in ('moderator', 'marketplace_admin', 'owner'))


def require_staff(session, user):
    if not staff(session, user):
        raise HTTPException(403, 'marketplace moderation permission required')


def require_unrestricted(session, user):
    profile = session.get(MarketplaceProfile, user.id)
    if profile and profile.restricted:
        raise HTTPException(403, 'marketplace access is restricted')


def require_owner(listing, user):
    if listing.seller_id != user.id:
        raise HTTPException(404, 'listing not found')


def require_version(listing, version):
    if listing.version != version:
        raise HTTPException(409, 'This listing has changed. Refresh before trying again.')


def require_live():
    if not capabilities()['public_listings_enabled']:
        raise HTTPException(409, 'Public listings and inquiries are not enabled. The marketplace is in preview.')
