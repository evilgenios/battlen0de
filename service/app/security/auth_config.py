"""Explicit, fail-closed authentication configuration. Default is production."""
import os

VALID_ROLES = frozenset({'member', 'admin'})


def local_auth_enabled() -> bool:
    environment = os.environ.get('APP_ENV', 'production').strip().lower()
    mode = os.environ.get('AUTH_MODE', 'session').strip().lower()
    if environment not in ('production', 'development', 'test'):
        raise RuntimeError('APP_ENV must be production, development or test')
    if mode not in ('session', 'local'):
        raise RuntimeError('AUTH_MODE must be session or local')
    if environment == 'production':
        if mode != 'session':
            raise RuntimeError('Production rejects AUTH_MODE=local')
        if os.environ.get('DASHBOARD_COOKIE_SECURE', 'true').lower() not in ('true', '1', 'yes'):
            raise RuntimeError('Production requires secure dashboard cookies')
    if mode == 'local':
        if not os.environ.get('DEV_USER_EMAIL', '').strip():
            raise RuntimeError('Local authentication requires DEV_USER_EMAIL')
        if os.environ.get('DEV_USER_ROLE', 'member') not in VALID_ROLES:
            raise RuntimeError('DEV_USER_ROLE must be member or admin')
    return mode == 'local'
