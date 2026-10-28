"""Unit tests for app/core/dashboard_session.py — no FastAPI, no real
sessions, no database."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi import HTTPException

from app.core.dashboard_session import DashboardSessionStore

USER_ID = uuid.uuid4()


def test_create_and_get_round_trip():
    store = DashboardSessionStore()
    session = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    assert store.get(session.session_id) is session


def test_get_unknown_session_returns_none():
    store = DashboardSessionStore()
    assert store.get('not-a-real-session-id') is None


def test_get_empty_session_id_returns_none():
    store = DashboardSessionStore()
    assert store.get('') is None


def test_destroy_makes_the_session_unusable():
    store = DashboardSessionStore()
    session = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    store.destroy(session.session_id)
    assert store.get(session.session_id) is None


def test_session_expires_after_absolute_ttl():
    store = DashboardSessionStore(ttl_seconds=0, idle_timeout_seconds=999)
    session = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    time.sleep(0.01)
    assert store.get(session.session_id) is None


def test_session_expires_after_idle_timeout_even_within_ttl():
    """A session that hasn't been used in a while must expire even though
    it's well within its absolute lifetime — this is what last_used_at
    exists for."""
    store = DashboardSessionStore(ttl_seconds=999, idle_timeout_seconds=0)
    session = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    time.sleep(0.01)
    assert store.get(session.session_id) is None


def test_using_a_session_refreshes_its_idle_clock():
    store = DashboardSessionStore(ttl_seconds=999, idle_timeout_seconds=999)
    session = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    before = session.last_used_at
    time.sleep(0.01)
    store.get(session.session_id)
    assert store.get(session.session_id).last_used_at > before


def test_active_count_reflects_live_sessions_and_excludes_destroyed_ones():
    store = DashboardSessionStore()
    assert store.active_count() == 0
    a = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    store.create(user_id=USER_ID, email='b@example.com', role='admin')
    assert store.active_count() == 2
    store.destroy(a.session_id)
    assert store.active_count() == 1


def test_each_session_gets_a_unique_unpredictable_id_and_csrf_token():
    store = DashboardSessionStore()
    a = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    b = store.create(user_id=USER_ID, email='a@example.com', role='admin')
    assert a.session_id != b.session_id
    assert a.csrf_token != b.csrf_token
    assert len(a.session_id) >= 32


def test_throttle_blocks_after_fixed_window_limit():
    store = DashboardSessionStore()
    store.throttle('api-write-minute', USER_ID, limit=2, seconds=60)
    store.throttle('api-write-minute', USER_ID, limit=2, seconds=60)
    with pytest.raises(HTTPException) as exc:
        store.throttle('api-write-minute', USER_ID, limit=2, seconds=60)
    assert exc.value.status_code == 429
    assert exc.value.headers['Retry-After'] == '60'
