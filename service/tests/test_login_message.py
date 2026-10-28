"""Login message construction using per-session credentials.

This is the specific claim the whole refactor rests on: build_login_message()
must read self.credentials, never a module-level global. These tests parse
the real serialized up_msg bytes with the real up_pb2 classes — nothing
about the protobuf encoding is mocked, only credentials are test fakes.
"""

from app.core.warpath import connection as connection_module
from app.core.warpath.connection import WarpathConnection
from app.core.warpath.protobuf import up_pb2


def test_login_message_fields_match_this_accounts_credentials(make_credentials):
    creds = make_credentials('account-a', profile_uid=555, platform=22)
    conn = WarpathConnection(creds)

    raw = conn.build_login_message()
    up = up_pb2.up_msg()
    up.ParseFromString(raw)

    assert up.sdk_login.sdk_session_key == creds.app_token
    assert up.sdk_login.plat == creds.platform
    assert up.sdk_login.oss_common.open_id == creds.app_uid
    assert up.sdk_login.oss_common.device_id == creds.device_id
    assert up.sdk_login.oss_common.idfa == creds.device_id
    assert up.sdk_login.oss_common.game_id == creds.game_id
    assert up.sdk_login.oss_common.pack_name == creds.pack_name
    assert up.sdk_login.oss_common.channel_id == creds.channel_id
    assert up.sdk_login.oss_common.app_version == creds.app_version
    assert up.sdk_login.oss_common.os_type == creds.os_type


def test_two_connections_never_leak_credentials_into_each_others_login_message(make_credentials):
    creds_a = make_credentials('account-a', app_uid='uid-a-only', app_token='token-a-only')
    creds_b = make_credentials('account-b', app_uid='uid-b-only', app_token='token-b-only')

    conn_a = WarpathConnection(creds_a)
    conn_b = WarpathConnection(creds_b)

    # Interleave the calls deliberately: if build_login_message() ever read
    # a module-level global instead of self.credentials, constructing/using
    # B in between A's two calls would corrupt A's second message.
    msg_a1 = up_pb2.up_msg()
    msg_a1.ParseFromString(conn_a.build_login_message())

    msg_b = up_pb2.up_msg()
    msg_b.ParseFromString(conn_b.build_login_message())

    msg_a2 = up_pb2.up_msg()
    msg_a2.ParseFromString(conn_a.build_login_message())

    assert msg_a1.sdk_login.oss_common.open_id == 'uid-a-only'
    assert msg_a2.sdk_login.oss_common.open_id == 'uid-a-only'
    assert msg_b.sdk_login.oss_common.open_id == 'uid-b-only'
    assert msg_a1.sdk_login.sdk_session_key != msg_b.sdk_login.sdk_session_key


def test_connection_constructor_requires_credentials(make_credentials):
    creds = make_credentials('account-a')
    conn = WarpathConnection(creds)
    assert conn.credentials is creds


def test_no_module_level_credential_globals_in_connection_module():
    """Guards the core requirement of stage 1: connection.py must not fall
    back to module-level WARPATH_*/SERVER_IP/GAME_ID globals the way the
    original warpath_bot.py did."""
    forbidden_names = {
        'WARPATH_APP_UID', 'WARPATH_APP_TOKEN', 'WARPATH_DEVICE_ID',
        'WARPATH_PROFILE_UID', 'WARPATH_PLATFORM', 'WARPATH_OS_TYPE',
        'WARPATH_OS_VERSION', 'WARPATH_APP_VERSION', 'WARPATH_PACK_NAME',
        'WARPATH_CHANNEL_ID', 'SERVER_IP', 'SERVER_PORT', 'GAME_ID',
    }
    present = forbidden_names & set(vars(connection_module))
    assert not present, f'connection.py still defines module-level credential globals: {present}'
