import types

import pytest

from dihlibs.superset_api import SupersetAPI


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.content = content

    def json(self):
        return self._json_data


@pytest.fixture
def mock_secrets(monkeypatch):
    secrets = {
        "test": {"url": "http://superset", "username": "user", "password": "pass"}
    }
    monkeypatch.setattr(
        "dihlibs.superset_api.fn.load_secret_file", lambda *_, **__: secrets
    )
    return secrets


def test_login_sets_tokens(monkeypatch, mock_secrets):
    def fake_post(url, *args, **kwargs):
        assert url == "http://superset/api/v1/security/login"
        return MockResponse(
            json_data={"access_token": "token123", "refresh_token": "refresh456"}
        )

    monkeypatch.setattr("dihlibs.superset_api.requests.post", fake_post)
    api = SupersetAPI("test")

    response = api.login()

    assert response.status_code == 200
    assert api.access_token == "token123"
    assert api._refresh_token == "refresh456"


def test_refresh_access_token_updates_token(monkeypatch, mock_secrets):
    calls = []

    def fake_post(url, *args, **kwargs):
        calls.append(url)
        if url.endswith("/security/login"):
            return MockResponse(json_data={"access_token": "initial", "refresh_token": "refresh"})
        if url.endswith("/security/refresh"):
            return MockResponse(json_data={"access_token": "new-token", "refresh_token": "refresh-2"})
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("dihlibs.superset_api.requests.post", fake_post)
    api = SupersetAPI("test")
    api.login()

    refreshed = api.refresh_access_token()

    assert refreshed is True
    assert api.access_token == "new-token"
    assert api._refresh_token == "refresh-2"
    assert calls.count("http://superset/api/v1/security/refresh") == 1


def test_post_retries_after_auth_failure(monkeypatch, mock_secrets):
    post_calls = []

    responses = {
        "http://superset/api/v1/security/login": [
            MockResponse(json_data={"access_token": "token1", "refresh_token": "refresh1"}),
            MockResponse(json_data={"access_token": "token2", "refresh_token": "refresh2"}),
        ],
        "http://superset/resource": [
            MockResponse(status_code=401),
            MockResponse(status_code=200, json_data={"ok": True}),
        ],
    }

    def fake_post(url, *args, **kwargs):
        post_calls.append(url)
        queue = responses.get(url)
        if not queue:
            raise AssertionError(f"No response stub for {url}")
        return queue.pop(0)

    monkeypatch.setattr("dihlibs.superset_api.requests.post", fake_post)
    monkeypatch.setattr("dihlibs.superset_api.fn.has_expired_client_side", lambda token: False)

    api = SupersetAPI("test")
    result = api.post("/resource")

    assert result.status_code == 200
    assert post_calls.count("http://superset/resource") == 2
    assert post_calls.count("http://superset/api/v1/security/login") == 2
    assert api.access_token == "token2"
