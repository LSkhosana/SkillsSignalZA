"""Future authentication boundary.

This module is intentionally inactive. No route in this scaffold depends
on it.

Rules that must hold when authentication is implemented:

* Do not decode JWTs without verifying the signature against a trusted key.
* Do not trust user IDs or roles supplied by the client.
* Do not accept unsigned or locally minted tokens.
* Do not ship mock authentication that could be enabled in production.
"""

from typing import NoReturn


async def require_authenticated_principal() -> NoReturn:
    """Reject authentication until a verified identity flow exists.

    Raising ``NotImplementedError`` keeps this dependency unusable as a
    production bypass.
    """
    raise NotImplementedError(
        "Authentication is not implemented. Do not decode unsigned tokens "
        "or trust client-supplied user identifiers."
    )
