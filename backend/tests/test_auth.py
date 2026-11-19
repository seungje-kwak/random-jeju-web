"""US-004 token checks and FR-35 /me (tasks/prd-random-jeju-merge.md). Offline: a fake store, local keys."""
from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from typing import Optional

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth, main, store

SECRET = "test-secret-at-least-32-bytes-long!!"
ISSUER = "https://example.supabase.co/auth/v1"
EC_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeStore:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}

    def get_user(self, user_id: str) -> Optional[dict]:
        return self.users.get(user_id)

    def save_nickname(self, user_id: str, nickname: str) -> dict:
        row = self.users.setdefault(user_id, {"id": user_id})
        row["nickname"] = nickname
        return row


class FakeJwks:
    def get_signing_key_from_jwt(self, token: str):
        return SimpleNamespace(key=EC_KEY.public_key())


def token(sub: Optional[str] = None, *, alg: str = "HS256", key=SECRET, exp_in: int = 3600, role: str = "authenticated",
          aud: str = "authenticated", iss: str = ISSUER, anonymous: bool = True, **extra) -> str:
    claims = {"sub": sub or str(uuid.uuid4()), "role": role, "aud": aud, "iss": iss,
              "exp": int(time.time()) + exp_in, "iat": int(time.time()), "is_anonymous": anonymous, **extra}
    return jwt.encode(claims, key, algorithm=alg)


@pytest.fixture()
def fake_store(monkeypatch):
    fs = FakeStore()
    monkeypatch.setattr(store, "_store", fs)
    return fs


@pytest.fixture()
def client(fake_store, monkeypatch):
    monkeypatch.setattr(auth, "_verifier", auth.TokenVerifier(secret=SECRET, jwks=FakeJwks(), issuer=ISSUER))
    with TestClient(main.app) as c:
        yield c


def bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def code(res) -> str:
    return res.json()["detail"]["code"]


# --- the four cases US-004 names ---------------------------------------------------------------------
def test_valid_token_gives_the_user(client):
    uid = str(uuid.uuid4())
    res = client.get("/me", headers=bearer(token(uid)))
    assert res.status_code == 200
    assert res.json() == {"user_id": uid, "nickname": None, "is_anonymous": True}


def test_expired_token_is_401(client):
    res = client.get("/me", headers=bearer(token(exp_in=-120)))   # past the 30 s leeway
    assert res.status_code == 401 and code(res) == "UNAUTHORIZED"


def test_wrong_signature_is_401(client):
    res = client.get("/me", headers=bearer(token(key="another-secret-that-is-32-bytes-long")))
    assert res.status_code == 401 and code(res) == "UNAUTHORIZED"


def test_no_token_is_401(client):
    res = client.get("/me")
    assert res.status_code == 401 and code(res) == "UNAUTHORIZED"


# --- other ways a token can be wrong -------------------------------------------------------------------
@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer ", "Token abc", "Bearer not.a.jwt"])
def test_malformed_header_is_401(client, header):
    res = client.get("/me", headers={"Authorization": header})
    assert res.status_code == 401


def test_anon_api_key_is_not_a_user(client):
    # The public anon key is itself an HS256 token with role "anon" and no subject
    anon_key = jwt.encode({"role": "anon", "iss": "supabase", "exp": int(time.time()) + 3600}, SECRET, algorithm="HS256")
    assert client.get("/me", headers=bearer(anon_key)).status_code == 401


def test_service_role_token_is_not_a_user(client):
    assert client.get("/me", headers=bearer(token(role="service_role"))).status_code == 401


def test_wrong_audience_or_issuer_is_401(client):
    assert client.get("/me", headers=bearer(token(aud="other"))).status_code == 401
    assert client.get("/me", headers=bearer(token(iss="https://evil.example/auth/v1"))).status_code == 401


def test_unsigned_token_is_401(client):
    t = jwt.encode({"sub": str(uuid.uuid4()), "role": "authenticated", "aud": "authenticated", "iss": ISSUER,
                    "exp": int(time.time()) + 3600}, None, algorithm="none")
    assert client.get("/me", headers=bearer(t)).status_code == 401


def test_signing_key_token_works(client):
    uid = str(uuid.uuid4())
    res = client.get("/me", headers=bearer(token(uid, alg="ES256", key=EC_KEY, anonymous=False)))
    assert res.status_code == 200 and res.json()["user_id"] == uid and res.json()["is_anonymous"] is False


def test_signing_key_token_signed_by_another_key_is_401(client):
    other = ec.generate_private_key(ec.SECP256R1())
    assert client.get("/me", headers=bearer(token(alg="ES256", key=other))).status_code == 401


def test_hs256_without_a_secret_says_auth_is_not_set_up(fake_store, monkeypatch):
    monkeypatch.setattr(auth, "_verifier", auth.TokenVerifier(secret="", jwks=FakeJwks(), issuer=ISSUER))
    with TestClient(main.app) as c:
        res = c.get("/me", headers=bearer(token()))
    assert res.status_code == 503 and code(res) == "AUTH_NOT_CONFIGURED"


def test_user_id_in_the_query_is_ignored(client):
    uid, other = str(uuid.uuid4()), str(uuid.uuid4())
    res = client.get(f"/me?user_id={other}&userId={other}", headers=bearer(token(uid)))
    assert res.json()["user_id"] == uid


# --- FR-35 nickname -------------------------------------------------------------------------------------
def test_save_and_read_nickname(client, fake_store):
    uid = str(uuid.uuid4())
    res = client.post("/me", json={"nickname": "  귤좋아  "}, headers=bearer(token(uid)))
    assert res.status_code == 200 and res.json()["nickname"] == "귤좋아"
    assert fake_store.users[uid]["nickname"] == "귤좋아"
    assert client.get("/me", headers=bearer(token(uid))).json()["nickname"] == "귤좋아"


@pytest.mark.parametrize("name", ["a", " ", "x" * 13, "가나다라마바사아자차카타파", "a\nb", "ab​"])
def test_bad_nickname_is_422(client, name):
    res = client.post("/me", json={"nickname": name}, headers=bearer(token()))
    assert res.status_code == 422 and code(res) == "INVALID_NICKNAME"


@pytest.mark.parametrize("name", ["ab", "x" * 12, "Jeju Lover", "제주"])
def test_good_nickname_lengths(client, name):
    assert client.post("/me", json={"nickname": name}, headers=bearer(token())).status_code == 200


def test_saving_a_nickname_needs_a_token(client):
    assert client.post("/me", json={"nickname": "귤좋아"}).status_code == 401
