"""1.1 the local Neon-shaped EdDSA issuer matches the documented Neon Auth token contract."""
from __future__ import annotations

import jwt
from jwt import PyJWK

from wearhouse.testing import LocalIssuer

ORIGIN = "https://ep-wearhouse-test.aws.neon.tech"


def test_neon_shaped_token_decodes_with_eddsa_and_published_jwk():
    iss = LocalIssuer.neon(ORIGIN)
    token = iss.token("0b0f6a1e-user", profile={"image": "https://lh3.googleusercontent.com/a/x"})
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "EdDSA" and header["kid"] == iss.current_kid
    jwk = next(k for k in iss.jwks()["keys"] if k["kid"] == header["kid"])
    assert (jwk["kty"], jwk["crv"], jwk["alg"]) == ("OKP", "Ed25519", "EdDSA")
    claims = jwt.decode(token, PyJWK(jwk).key, algorithms=["EdDSA"], issuer=ORIGIN, audience=ORIGIN)
    assert claims["iss"] == claims["aud"] == ORIGIN
    assert claims["sub"] == claims["id"] == "0b0f6a1e-user"
    assert claims["exp"] - claims["iat"] == 900
    for k in ("name", "email", "emailVerified", "image", "role", "banned"):
        assert k in claims
    assert claims["role"] == "authenticated" and claims["banned"] is False


def test_rs256_issuer_unchanged():
    iss = LocalIssuer()
    token = iss.token("a")
    assert jwt.get_unverified_header(token)["alg"] == "RS256"
    assert "email" not in jwt.decode(token, options={"verify_signature": False})
