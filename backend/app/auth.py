"""Who is calling (tasks/prd-random-jeju-merge.md US-004).

The browser signs in to Supabase Auth (anonymously or not) and sends `Authorization: Bearer <access_token>`.
The token is checked here; a user ID is never read from a query string or a request body.

- HS256 tokens are checked with SUPABASE_JWT_SECRET (projects on the legacy shared secret).
- ES256 / RS256 tokens are checked with the project's published signing keys (AUTH_JWKS_URL).
The algorithm in the token header only picks which of the two keys to use; each key accepts only its
own algorithms, so a token cannot switch an asymmetric key into an HMAC secret.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import jwt
from fastapi import Header

from . import config
from .errors import ApiError

log = logging.getLogger("mypace.auth")

ASYMMETRIC_ALGS = ("ES256", "RS256", "EdDSA")


@dataclass(frozen=True)
class User:
    id: str
    is_anonymous: bool


class SigningKeys(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class TokenVerifier:
    def __init__(self, secret: str = "", jwks: Optional[SigningKeys] = None, issuer: str = "",
                 audience: str = config.AUTH_AUDIENCE, leeway: int = config.AUTH_LEEWAY_SEC) -> None:
        self.secret = secret
        self.jwks = jwks
        self.issuer = issuer
        self.audience = audience
        self.leeway = leeway

    def verify(self, token: str) -> User:
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError:
            raise _unauthorized()
        if alg == "HS256":
            if not self.secret:
                log.error("HS256 token received but SUPABASE_JWT_SECRET is not set")
                raise ApiError(503, "AUTH_NOT_CONFIGURED", "Sign-in is not set up on the server.")
            key: Any = self.secret
        elif alg in ASYMMETRIC_ALGS and self.jwks is not None:
            try:
                key = self.jwks.get_signing_key_from_jwt(token).key
            except jwt.PyJWTError:
                raise _unauthorized()
        else:
            raise _unauthorized()
        try:
            claims = jwt.decode(
                token, key, algorithms=[alg], audience=self.audience,
                issuer=self.issuer or None, leeway=self.leeway,
                options={"require": ["exp", "sub", "aud"], "verify_iss": bool(self.issuer)},
            )
        except jwt.PyJWTError:
            raise _unauthorized()
        # The anon / service API keys are tokens too; only a signed-in user's token is accepted.
        if claims.get("role") != "authenticated" or not claims.get("sub"):
            raise _unauthorized()
        return User(id=str(claims["sub"]), is_anonymous=bool(claims.get("is_anonymous", False)))


def _unauthorized() -> ApiError:
    return ApiError(401, "UNAUTHORIZED", "Sign-in required.")


_verifier: Optional[TokenVerifier] = None


def get_verifier() -> TokenVerifier:
    global _verifier
    if _verifier is None:
        jwks = jwt.PyJWKClient(config.AUTH_JWKS_URL, cache_keys=True, lifespan=3600) if config.AUTH_JWKS_URL else None
        _verifier = TokenVerifier(secret=config.SUPABASE_JWT_SECRET, jwks=jwks, issuer=config.AUTH_ISSUER)
    return _verifier


def _token(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    return token.strip()


def current_user(authorization: Optional[str] = Header(default=None)) -> User:
    """For endpoints that need a signed-in user: 401 without a valid token."""
    if not authorization:
        raise _unauthorized()
    return get_verifier().verify(_token(authorization))


def optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[User]:
    """For endpoints anyone may call: None without a token, 401 with a bad one."""
    if not authorization:
        return None
    return get_verifier().verify(_token(authorization))
