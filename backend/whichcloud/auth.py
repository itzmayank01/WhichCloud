"""Who is calling. Verified, not asserted.

Every route that touches per-person data used to take an `owner` string from
the request -- in the body for a save, in the query string for a list or a
delete. `SaveArchitectureIn` was honest about it:

    `owner` arrives from the caller rather than being derived from a token.
    The identity provider sits in front of this service, and the browser never
    reaches it directly -- but that means this endpoint trusts its caller, so
    it must not be exposed publicly without a check in front of it.

The premise did not hold. The browser DOES reach this service: the frontend
calls it directly from the client, and `NEXT_PUBLIC_API_URL` is public by
construction. So `?owner=someone-else` read another person's saved
architectures, and a DELETE with the same parameter removed them. That is a
cross-tenant bug that shipped, not a hypothetical.

This module makes identity a property of the REQUEST'S SIGNATURE rather than
of its contents. The caller sends the Clerk session token; we verify it
against Clerk's published keys and take the subject from the verified claims.
A caller can no longer name themselves.
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, Header, HTTPException

#: Clerk's JWKS endpoint for this instance. Derived from the publishable key's
#: frontend API host, or set directly when that is not convenient.
#:
#: Deliberately has no default. A fallback here would mean a misconfigured
#: deployment silently verifying nothing, which is worse than refusing to
#: start: the failure would look like everything working.
JWKS_URL = os.getenv("CLERK_JWKS_URL", "")

#: Optional, and worth setting. Clerk puts the frontend origin in `azp`; a
#: token minted for a different application on the same Clerk instance will
#: verify cryptographically and still not belong here.
AUTHORIZED_PARTIES = [
    party.strip()
    for party in os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",")
    if party.strip()
]


class AuthError(HTTPException):
    def __init__(self, detail: str) -> None:
        # 401 rather than 403: the caller has not proved who they are. 403
        # would say "we know you and you may not", which is a different and
        # more informative answer than this service is in a position to give.
        super().__init__(status_code=401, detail=detail)


@lru_cache(maxsize=1)
def _jwk_client():
    """Clerk's signing keys, fetched once and cached.

    PyJWKClient keeps its own cache and re-fetches on an unknown key id, which
    is what makes key rotation a non-event: a token signed with a new key
    misses the cache, triggers one fetch, and verifies.
    """
    from jwt import PyJWKClient

    if not JWKS_URL:
        raise AuthError(
            "CLERK_JWKS_URL is not set, so no caller can be verified. "
            "Set it to your instance's .well-known/jwks.json."
        )
    return PyJWKClient(JWKS_URL, cache_keys=True)


def verify(token: str) -> dict:
    """The claims, or an AuthError. Never a partially trusted result."""
    import jwt

    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # Clerk session tokens carry no `aud`, so audience checking is off
            # and `azp` below does that job instead.
            options={"verify_aud": False, "require": ["exp", "sub"]},
            leeway=5,  # tolerate small clock skew between us and Clerk
        )
    except AuthError:
        raise
    except Exception as exc:  # jwt raises a family of these
        raise AuthError(f"Session token rejected: {str(exc)[:120]}") from exc

    if AUTHORIZED_PARTIES:
        party = claims.get("azp")
        if party and party not in AUTHORIZED_PARTIES:
            raise AuthError("Session token was issued for a different application.")

    subject = claims.get("sub")
    if not subject:
        raise AuthError("Session token carries no subject.")
    return claims


def current_owner(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: the caller's user id, proven.

    Returned as the same opaque string the frontend used to send, so every
    store call keeps working -- what changed is where it comes from.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Send the Clerk session token as `Authorization: Bearer <token>`.")
    return str(verify(authorization.split(" ", 1)[1].strip())["sub"])


#: The allow-list this used to be is gone, because the thing it stood in for
#: now exists. FinOps Live ran on one set of AWS credentials held by the
#: server, so `account_id` selected nothing and every signed-in user reached
#: the same real account; an explicit list of permitted Clerk subjects was the
#: only thing keeping that account away from anyone who signed up.
#:
#: Reads and destructive actions now run on credentials assumed from the
#: caller's OWN connection (see `_aws_credentials_for` in api.py and the
#: ContextVar in connections/aws_live.py, which raises rather than falling
#: back to the host's credentials). Isolation therefore comes from the
#: connection lookup -- no connection, no data, and never anybody else's --
#: which is both stronger than the list and does not require an operator to
#: add each new user by hand.
#:
#: Authentication is still required: this is `current_owner` under a name the
#: FinOps routes already use, kept so the intent stays greppable at each call
#: site rather than becoming an anonymous `current_owner` among many.


def finops_owner(owner: str = Depends(current_owner)) -> str:
    """FastAPI dependency: the verified caller, for the FinOps routes.

    Access to any particular account is decided further in, by whether this
    owner has a connection to it -- see the note above.
    """
    return owner
