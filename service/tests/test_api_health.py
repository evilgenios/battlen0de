from fastapi.testclient import TestClient

from app.main import create_app
from tests.fake_repository import FakeEngine, InMemoryAccountRepository
from tests.fakes import synthetic_account_manager as AccountManager


def _client(*, healthy: bool) -> TestClient:
    app = create_app(lifespan_context=None)
    app.state.repository = InMemoryAccountRepository()
    app.state.account_manager = AccountManager()
    app.state.engine = FakeEngine(healthy=healthy)
    return TestClient(app)


def test_health_ok_when_database_reachable():
    with _client(healthy=True) as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'database': 'ok', 'auth_required': True}


def test_health_reports_auth_required_once_a_dashboard_user_exists():
    from app.security.passwords import hash_password

    with _client(healthy=True) as client:
        repo = client.app.state.repository
        repo.set_user_password('admin@example.com', password_hash=hash_password('correct horse battery staple'), role='admin')
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json()['auth_required'] is True


def test_health_503_when_database_unreachable():
    with _client(healthy=False) as client:
        response = client.get('/health')
        assert response.status_code == 503


def test_health_does_not_require_authentication():
    # /health must work even when DEV_USER_EMAIL is unset — it's a
    # liveness/readiness probe, not an account-scoped endpoint.
    with _client(healthy=True) as client:
        response = client.get('/health')
        assert response.status_code == 200
