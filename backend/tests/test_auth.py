from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from tests.conftest import PASSWORD


def test_password_hashing_is_salted_and_verifies():
    h1, h2 = hash_password("s3cret-value!"), hash_password("s3cret-value!")
    assert h1 != h2 and h1.startswith("$argon2id$")
    assert verify_password(h1, "s3cret-value!")
    assert not verify_password(h1, "wrong")
    assert not verify_password("not-a-hash", "anything")


def test_login_success_returns_token_and_sets_httponly_cookie(client):
    r = client.post("/auth/login", json={"email": "DR.RAO@careflow.demo", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "DOCTOR" and "ml:read" in body["user"]["permissions"]
    cookie = r.headers["set-cookie"].lower()
    assert "careflow_session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_login_failure_is_generic(client):
    wrong_pw = client.post("/auth/login", json={"email": "dr.rao@careflow.demo", "password": "nope"})
    no_user = client.post("/auth/login", json={"email": "ghost@careflow.demo", "password": "nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


def test_login_rate_limited_after_repeated_failures(client):
    codes = [client.post("/auth/login", json={"email": "nurse.kim@careflow.demo", "password": "bad"}).status_code
             for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_requests_without_or_with_bad_tokens_are_rejected():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)  # fresh client: no session cookie
    assert client.get("/patients").status_code == 401
    assert client.get("/patients", headers={"Authorization": "Bearer garbage"}).status_code == 401
    s = get_settings()
    expired = jwt.encode({"sub": "1", "iat": datetime.now(UTC) - timedelta(hours=2),
                          "exp": datetime.now(UTC) - timedelta(hours=1)}, s.jwt_secret, algorithm="HS256")
    r = client.get("/patients", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["error"]["message"].lower()
    forged = jwt.encode({"sub": "1", "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)},
                        "another-secret-that-is-long-enough-000000", algorithm="HS256")
    assert client.get("/patients", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_roundtrip_contains_required_claims():
    token, ttl = create_access_token(42, "NURSE")
    claims = decode_access_token(token)
    assert claims["sub"] == "42" and claims["role"] == "NURSE" and ttl > 0 and "jti" in claims


def test_cookie_session_requires_csrf_header_for_writes(client, tokens):
    from fastapi.testclient import TestClient

    from app.main import app

    browser = TestClient(app)
    browser.cookies.set("careflow_session", tokens["reception"])
    assert browser.get("/auth/me").status_code == 200  # safe method: cookie alone is enough
    body = {"first_name": "Cookie", "last_name": "Test", "date_of_birth": "1990-01-01", "sex": "F"}
    assert browser.post("/patients", json=body).status_code == 403
    assert browser.post("/patients", json=body, headers={"X-CareFlow-CSRF": "1"}).status_code == 201


def test_me_and_logout(client, auth):
    r = client.get("/auth/me", headers=auth("nurse"))
    assert r.status_code == 200 and r.json()["role"] == "NURSE"
    assert client.post("/auth/logout", headers=auth("nurse")).status_code == 204


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in r.headers
