"""Bearer-token auth for anything that changes the display.

The box binds to the network so connectors can reach it, which means the API is
exposed to whatever the Pi is attached to. A Tailscale ACL is the real boundary;
this is the second one, and it costs a single dependency.

Auth is off when BOX_TOKEN is unset, so local development is unchanged.
"""

import hmac
import logging

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


def _configured_token(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    return settings.token if settings is not None else ""


def require_token(request: Request) -> None:
    """Reject writes without a valid bearer token, when one is configured."""
    expected = _configured_token(request)
    if not expected:
        return

    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Constant-time compare so a wrong token cannot be guessed byte by byte.
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


#: Attach to any route that mutates the panel.
Protected = Depends(require_token)
