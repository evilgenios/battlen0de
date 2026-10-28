"""Lilith account-SDK client used to link a new Warpath account: a plain
HTTPS client that emails a 6-digit code to an address and exchanges it for
an (app_uid, app_token) pair.

Behavior is unchanged from the original warpath_bot.py. The one structural
change: the original read module globals / the first entry in a global
account store to decide which account "vouches" for the HTTPS request
(``_vehicle_identity()`` reading WARPATH_APP_UID/WARPATH_APP_TOKEN or
``stored_accounts()``). That was itself a single-account assumption baked
into the linking flow. Here the caller passes that vehicle account's
WarpathCredentials explicitly — callers (AccountManager, a future FastAPI
endpoint, the Discord bot) decide which already-connected account to use,
instead of this module guessing from global state.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .credentials import WarpathCredentials

LILITH_API_BASE = 'https://app.lilithgame.com'
LILITH_APP_ID = '9130660'
LILITH_GAME_ID = '10048'
LILITH_BUNDLE_ID = 'com.wondergames.warpath.ios'
LILITH_SDK_VERSION = '6.8.0.2'
LILITH_APP_VERSION = '14.20.0000'
LILITH_ENV_ID = 'prod15c4fd9be6fc7391da8f42f01173'
LILITH_CHANNEL_ID = 'self-lilith-0.7'
LILITH_USER_AGENT = (
    f'Warpath/{LILITH_APP_VERSION} ({LILITH_BUNDLE_ID}; build:1; '
    'iOS 26.4.0) Alamofire/5.9.1'
)
LILITH_REQUEST_TIMEOUT_SECONDS = 15

# Public key shipped inside LLHSDKCoreKit.framework — public material, used
# only to encrypt the email address exactly like the official client does.
_LILITH_RSA_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxg4zVvb+2O834B7JdaYS
HikiyzHc9irZrMBEd1RQOljNQnpCoXD+f1mPQyEXBzBUH5ikpBw2i92HVCfB8DlH
Q7lQQmTjpTWHIJ40UNpYP3sb+Hxd7Ze0ascv5hdYGXjnI3/vOIgoDnS5YAuwwYZJ
3f0+2iKOR9LaNZB/dgHYkpHSOWKMJ+eie9IaRbQ1iflNWWPbpU2f4BUIPiAi+xdP
st/hep3okIoo8NB5t3lbvPugfHpZ2C0CaSETRPNYue6xHiGAYRrJjPQh5fmKENJW
UY5H1w47DSH+fBpLai6CQkNgp73Gs1dnaODB5DI3DAIjkpN+gAbuZjZ/nM36cfgL
6QIDAQAB
-----END PUBLIC KEY-----"""


class LilithLoginError(Exception):
    pass


@dataclass
class LinkSession:
    """One device/session identity generated for both halves (send code +
    verify code) of one account-linking attempt. Not a credential — this is
    thrown away once verify_login_code succeeds or the attempt expires."""

    device_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    idfa: str = field(default_factory=lambda: uuid.uuid4().hex)
    install_id: str = ''
    sdk_session_id: str = ''
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.install_id:
            self.install_id = f'{self.device_id}-{int(self.created_at)}'
        if not self.sdk_session_id:
            self.sdk_session_id = f'{uuid.uuid4()}'.upper() + f'-{int(self.created_at * 1000)}'

    @classmethod
    def new(cls) -> 'LinkSession':
        return cls()


def _requests_module():
    try:
        import requests
    except ImportError:
        raise RuntimeError("The 'requests' package is required for account linking: pip install requests")
    return requests


def _encrypt_email(email: str) -> str:
    key = serialization.load_pem_public_key(_LILITH_RSA_PUBLIC_KEY_PEM)
    ciphertext = key.encrypt(email.encode('utf-8'), padding.PKCS1v15())
    return base64.b64encode(ciphertext).decode('ascii')


def _headers(request_id: str, form: bool) -> dict:
    return {
        'accept': '*/*',
        'content-type': (
            'application/x-www-form-urlencoded; charset=utf-8' if form else 'application/json'
        ),
        'accept-language': 'en-US;q=1.0',
        'x-request-id': request_id,
        'user-agent': LILITH_USER_AGENT,
    }


def _response_data(response, default_error: str) -> dict:
    """Validate the response while accepting both known Lilith result shapes."""
    try:
        payload = response.json()
    except (TypeError, ValueError) as error:
        raise LilithLoginError('Lilith returned a non-JSON response') from error
    if not isinstance(payload, dict):
        raise LilithLoginError('Lilith returned an invalid response')

    result = payload.get('result')
    if isinstance(result, dict):
        code = result.get('code')
        message = result.get('msg') or result.get('message')
        nested_data = result.get('data')
    else:
        code = result if result is not None else payload.get('code')
        message = payload.get('msg') or payload.get('message')
        nested_data = None

    try:
        succeeded = int(code) == 0
    except (TypeError, ValueError):
        succeeded = False
    if not succeeded:
        raise LilithLoginError(str(message or default_error))

    data = payload.get('data')
    if not isinstance(data, dict):
        data = nested_data if isinstance(nested_data, dict) else {}
    return data


def send_login_code(
    vehicle: WarpathCredentials,
    email: str,
    link_session: Optional[LinkSession] = None,
) -> LinkSession:
    """Ask Lilith to email a 6-digit login code to ``email``.

    ``vehicle`` is any already-authenticated account's credentials — Lilith
    requires *some* valid (app_uid, app_token) to authorize the request even
    though it is not the account being linked. Never reuse the target
    account's own (not-yet-issued) credentials here; there aren't any yet.
    """
    requests = _requests_module()
    if not vehicle.app_uid or not vehicle.app_token:
        raise LilithLoginError(
            'No authenticated account available to authorize the link request '
            '(vehicle credentials are missing app_uid/app_token).'
        )
    link_session = link_session or LinkSession.new()
    body = {
        'isAuthorized': '0',
        'real_package_name': LILITH_BUNDLE_ID,
        'env_id': LILITH_ENV_ID,
        'os_type': 'mac',
        'app_uid': int(vehicle.app_uid),
        'sdk_build_code': '0',
        'app_id': int(LILITH_APP_ID),
        'sdk_session_id': link_session.sdk_session_id,
        'att_status': 2,
        'device_name': 'iPad',
        'os_version': '26.4.0',
        'device_model': 'iPad16,6',
        'pack_name': LILITH_BUNDLE_ID,
        'install_id': link_session.install_id,
        'app_token': vehicle.app_token,
        'store_country': 'US',
        'mcc_codes': '',
        'lilith_language': 'en',
        'idfa': link_session.idfa,
        'timezone': 'Europe/Vienna',
        'channel_id': LILITH_CHANNEL_ID,
        'is_jailbreak': '0',
        'device_country_code': 'US',
        'lang': 'en',
        'system_language': 'en',
        'device_id': link_session.device_id,
        'scene': 'login',
        'type': 'email',
        'app_bundle_id': LILITH_BUNDLE_ID,
        'device_brand': 'Apple',
        'app_version': LILITH_APP_VERSION,
        'sdk_version': LILITH_SDK_VERSION,
        'game_id': LILITH_GAME_ID,
        'account': _encrypt_email(email),
    }
    response = requests.post(
        f'{LILITH_API_BASE}/api/park/sdk/account/send_auth_code',
        json=body,
        headers=_headers(str(uuid.uuid4()).upper(), form=False),
        timeout=LILITH_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    _response_data(response, 'could not send verification code')
    return link_session


def verify_login_code(
    vehicle: WarpathCredentials,
    email: str,
    code: str,
    link_session: LinkSession,
) -> tuple[str, str]:
    """Exchange the emailed 6-digit code for (app_uid, app_token)."""
    requests = _requests_module()
    if not vehicle.app_uid or not vehicle.app_token:
        raise LilithLoginError(
            'No authenticated account available to authorize the verify request.'
        )
    body = {
        'app_bundle_id': LILITH_BUNDLE_ID,
        'app_id': LILITH_APP_ID,
        'app_token': vehicle.app_token,
        'app_uid': vehicle.app_uid,
        'app_version': LILITH_APP_VERSION,
        'att_status': '2',
        'auth_type': '0',
        'channel_id': LILITH_CHANNEL_ID,
        'device_brand': 'Apple',
        'device_country_code': 'US',
        'device_id': link_session.device_id,
        'device_model': 'iPad16,6',
        'device_name': 'iPad',
        'env_id': LILITH_ENV_ID,
        'game_id': LILITH_GAME_ID,
        'idfa': link_session.idfa,
        'install_id': link_session.install_id,
        'isAuthorized': '0',
        'is_jailbreak': '0',
        'lang': '2',
        'lilith_language': 'en',
        'login_mode': '1',
        'mcc_codes': '',
        'os_type': 'mac',
        'os_version': '26.4.0',
        'pack_name': LILITH_BUNDLE_ID,
        'pass': code,
        'player_id': email,
        'real_package_name': LILITH_BUNDLE_ID,
        'sdk_build_code': '0',
        'sdk_session_id': link_session.sdk_session_id,
        'sdk_version': LILITH_SDK_VERSION,
        'store_country': 'US',
        'system_language': 'en',
        'timezone': 'Europe/Vienna',
        'type': '1',
    }
    response = requests.post(
        f'{LILITH_API_BASE}/v2/api/sdk/login',
        data=body,
        headers=_headers(str(uuid.uuid4()).upper(), form=True),
        timeout=LILITH_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = _response_data(response, 'verification failed')
    uid = str(data.get('app_uid') or data.get('appUid') or '').strip()
    token = str(data.get('app_token') or data.get('appToken') or '').strip()
    if not uid or not token:
        raise LilithLoginError('verification reply did not contain credentials')
    return uid, token
