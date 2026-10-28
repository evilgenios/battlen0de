"""Canonical upstream identity; conservative one Lilith UID per account row."""
import re

CANONICAL_SQL = "CASE WHEN btrim(app_uid) ~ '^[0-9]{1,64}$' AND ltrim(btrim(app_uid), '0') <> '' THEN 'warpath:lilith:' || ltrim(btrim(app_uid), '0') ELSE NULL END"
ACCOUNT_STATUSES = frozenset({'active', 'disabled', 'needs_reauth', 'restricted'})


def canonical_identity(uid: str) -> str | None:
    value = uid.strip(' ')
    if not re.fullmatch(r'[0-9]{1,64}', value) or not value.lstrip('0'):
        return None
    return 'warpath:lilith:' + value.lstrip('0')


class IdentityConflict(Exception):
    """Generic: does not disclose another customer's identity or ownership."""


class AccountLimitReached(Exception):
    pass


class AccountUnavailable(Exception):
    pass
