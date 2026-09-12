"""The one credential this product holds, and how it is kept.

Two of the three providers are connected without giving us a secret at
all:

    AWS    we are trusted to call AssumeRole on a role the user creates.
           They can revoke it, and we never hold a key.
    GCP    they grant OUR service account read access to their billing
           export. Same shape: revocable, no key.

Azure has no equivalent. Reading Cost Management means a service
principal, and a service principal means a client secret that we store
and replay. That is a real, ongoing liability, and the honest response is
to encrypt it, to say so in the interface, and to make it impossible to
store one by accident on a deployment that was never configured to
protect it.

Hence no default key. A fallback would mean a misconfigured deployment
encrypting every secret under a value that is in the source tree, which
is indistinguishable from not encrypting them at all -- while looking
exactly like it works.
"""

from __future__ import annotations

import os
from functools import lru_cache


class SecretsUnavailable(RuntimeError):
    """Raised rather than storing a credential in the clear."""


#: A urlsafe base64 32-byte key, as produced by:
#:     python -c "from cryptography.fernet import Fernet;
#:                print(Fernet.generate_key().decode())"
KEY_ENV = "WHICHCLOUD_SECRETS_KEY"


@lru_cache(maxsize=1)
def _cipher():
    from cryptography.fernet import Fernet

    key = os.getenv(KEY_ENV, "").strip()
    if not key:
        raise SecretsUnavailable(
            f"{KEY_ENV} is not set, so a client secret cannot be stored "
            "safely. Generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and set it before '
            "connecting an Azure account. AWS and GCP need no secret and "
            "connect without it."
        )
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise SecretsUnavailable(
            f"{KEY_ENV} is not a valid Fernet key (needs 32 url-safe "
            f"base64-encoded bytes): {exc}"
        ) from exc


def available() -> bool:
    """Whether a secret could be stored right now.

    Asked BEFORE the interface offers Azure, so somebody is told the
    deployment cannot hold their credential before they go and create a
    service principal for it -- not after.
    """
    try:
        _cipher()
        return True
    except SecretsUnavailable:
        return False


def seal(plaintext: str) -> bytes:
    """Ciphertext for the database. Fernet: AES-128-CBC plus HMAC, so a
    tampered value fails to open rather than decrypting to rubbish."""
    if not plaintext:
        raise ValueError("Refusing to seal an empty secret.")
    return _cipher().encrypt(plaintext.encode())


def open_sealed(ciphertext: bytes | memoryview | None) -> str:
    """The plaintext, for the moment it takes to exchange it for a token.

    Never returned to a caller outside this process, never logged, and
    never sent back over the API -- a connection's secret is write-only
    from the interface's point of view.
    """
    if not ciphertext:
        return ""
    from cryptography.fernet import InvalidToken

    try:
        return _cipher().decrypt(bytes(ciphertext)).decode()
    except InvalidToken as exc:
        # Almost always a rotated or swapped key. Say which, because the
        # alternative reading -- a corrupt database -- sends somebody
        # looking in the wrong place.
        raise SecretsUnavailable(
            "A stored secret could not be decrypted with the current "
            f"{KEY_ENV}. If the key was rotated, the affected connections "
            "have to be re-authorised; the old ciphertext cannot be "
            "recovered without the old key."
        ) from exc
