"""Per-account Warpath credentials/config.

Everything here used to be a module-level global in warpath_bot.py
(WARPATH_APP_UID, WARPATH_APP_TOKEN, WARPATH_DEVICE_ID, WARPATH_PLATFORM,
SERVER_IP, ...), mutated in place via apply_sdk_account()/reset_sdk_account()
whenever the bot wanted to switch "the" active account. That made exactly
one account connectable at a time by construction.

WarpathCredentials replaces all of that with one immutable value object per
account. A WarpathConnection is handed exactly one of these at construction
and never reads process-global state for identity/session/device info again.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Mapping, Optional, Tuple

DEFAULT_SERVER_IP = '34.8.3.236'
DEFAULT_SERVER_PORT = 10000
DEFAULT_GAME_ID = '10048'


def _env_str(env: Mapping[str, str], name: str, default: str = '') -> str:
    return str(env.get(name, default) or '').strip()


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f'{name} must be an integer') from exc


@dataclass(frozen=True)
class WarpathCredentials:
    """Identity, session, device, and gateway config for exactly one
    Warpath account. One instance per account; never shared or mutated
    in place (use with_updates() to derive a new one, e.g. after a token
    refresh)."""

    # -- identity -------------------------------------------------------
    account_id: str          # internal id (e.g. a UUID); never the login email
    app_uid: str
    app_token: str
    device_id: str
    profile_uid: int = 0
    label: str = ''          # display name only (e.g. linked email/nickname)

    # -- platform / device metadata (feeds oss_common.*) -----------------
    platform: int = 22       # common.proto: self=0, iOS=15, Android=21, PC=22
    app_id: str = ''
    pack_name: str = ''
    channel_id: str = ''
    device_model: str = ''
    os_type: str = ''
    os_version: str = ''
    os_language: str = 'ENG'
    pack_language: str = 'ENG'
    timezone: int = 0
    app_version: str = ''
    package_version: str = ''
    env_id: str = ''
    net_route_type: int = 0
    net_route_info: str = ''
    client_ip: str = ''
    game_id: str = DEFAULT_GAME_ID

    # -- gateway ----------------------------------------------------------
    server_ip: str = DEFAULT_SERVER_IP
    server_port: int = DEFAULT_SERVER_PORT
    login_timeout: int = 30

    def secret_values(self) -> Tuple[str, ...]:
        """Values that must never appear in logs/error text/Discord replies."""
        return tuple(v for v in (self.app_token, self.device_id) if v)

    def __repr__(self) -> str:
        """Override the dataclass-generated repr, which would otherwise
        print app_token/device_id in plain text on any accidental
        logger.info(f"...{credentials}") or unhandled-exception traceback
        that has this object in a local variable. Only non-secret
        identifying fields are shown."""
        return (
            f'WarpathCredentials(account_id={self.account_id!r}, label={self.label!r}, '
            f'app_uid={self.app_uid!r}, platform={self.platform!r}, '
            f'app_token=<redacted>, device_id=<redacted>)'
        )

    __str__ = __repr__

    def validation_errors(self) -> list[str]:
        """Same checks as the original warpath_configuration_errors(), just
        against this account's own fields instead of module globals."""
        required = {
            'app_uid': self.app_uid,
            'app_token': self.app_token,
            'device_id': self.device_id,
            'app_id': self.app_id,
            'pack_name': self.pack_name,
            'channel_id': self.channel_id,
            'app_version': self.app_version,
            'package_version': self.package_version,
        }
        errors = [f'{name} is not set' for name, value in required.items() if not value]
        if self.platform not in {0, 15, 21, 22}:
            errors.append('platform must be 0, 15, 21, or 22')
        if self.platform == 22 and self.os_type not in {'win', 'pc'}:
            errors.append("PC credentials require os_type='win' (or 'pc')")
        if not self.server_ip:
            errors.append('server_ip is not set')
        if not 1 <= self.server_port <= 65535:
            errors.append('server_port must be between 1 and 65535')
        return errors

    def with_updates(self, **kwargs) -> 'WarpathCredentials':
        return replace(self, **kwargs)

    @classmethod
    def from_env(
        cls,
        account_id: str,
        *,
        prefix: str = 'WARPATH_',
        label: str = '',
        env: Optional[Mapping[str, str]] = None,
    ) -> 'WarpathCredentials':
        """Load one account's credentials from environment variables named
        ``<prefix><FIELD>`` (e.g. prefix='WARPATH_A_' -> WARPATH_A_APP_UID).

        This is the same variable *shape* the original .env used
        (WARPATH_APP_UID, WARPATH_DEVICE_ID, ...); the prefix is what lets
        two (or more) accounts live in one process's environment at once
        without colliding, e.g. WARPATH_A_* / WARPATH_B_*.
        """
        env = os.environ if env is None else env

        def key(name: str) -> str:
            return f'{prefix}{name}'

        app_uid = _env_str(env, key('APP_UID'))
        device_id = (
            _env_str(env, key('DEVICE_ID'))
            or _env_str(env, key('IDFA'))
            or _env_str(env, key('SESSION_HASH'))
        )
        platform = _env_int(env, key('PLATFORM'), 22)
        profile_uid_default = int(app_uid) if app_uid.isdigit() else 0

        return cls(
            account_id=account_id,
            label=label or account_id,
            app_uid=app_uid,
            app_token=_env_str(env, key('APP_TOKEN')),
            device_id=device_id,
            profile_uid=_env_int(env, key('PROFILE_UID'), profile_uid_default),
            platform=platform,
            app_id=_env_str(env, key('APP_ID')),
            pack_name=_env_str(env, key('PACK_NAME')),
            channel_id=_env_str(env, key('CHANNEL_ID')),
            device_model=_env_str(env, key('DEVICE_MODEL'), 'win' if platform == 22 else ''),
            os_type=_env_str(env, key('OS_TYPE'), 'win' if platform == 22 else ''),
            os_version=_env_str(env, key('OS_VERSION')),
            os_language=_env_str(env, key('OS_LANGUAGE'), 'ENG'),
            pack_language=_env_str(env, key('PACK_LANGUAGE'), 'ENG'),
            timezone=_env_int(env, key('TIMEZONE'), 0),
            app_version=_env_str(env, key('APP_VERSION')),
            package_version=_env_str(env, key('PACKAGE_VERSION')),
            env_id=_env_str(env, key('ENV_ID')),
            net_route_type=_env_int(env, key('NET_ROUTE_TYPE'), 0),
            net_route_info=_env_str(env, key('NET_ROUTE_INFO')),
            client_ip=_env_str(env, key('CLIENT_IP')),
            game_id=_env_str(env, key('GAME_ID'), DEFAULT_GAME_ID),
            server_ip=_env_str(env, key('SERVER_IP'), DEFAULT_SERVER_IP),
            server_port=_env_int(env, key('SERVER_PORT'), DEFAULT_SERVER_PORT),
            login_timeout=max(5, _env_int(env, key('LOGIN_TIMEOUT'), 30)),
        )


def redact_secrets(text: object, *credential_sets: WarpathCredentials) -> str:
    """Scrub every secret belonging to any of the given accounts out of
    ``text``. Pass every account whose secrets might plausibly appear (e.g.
    all sessions an AccountManager knows about) when logging/broadcasting
    across accounts; a single WarpathConnection only needs to pass its own.
    """
    cleaned = str(text).replace('\r', ' ').replace('\n', ' ').strip()
    for creds in credential_sets:
        for secret in creds.secret_values():
            cleaned = cleaned.replace(secret, '<redacted>')
    return (cleaned or 'unknown error')[:500]
