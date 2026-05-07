from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.remote import ApiToken
from app.services.remote import find_token_by_plaintext, mark_token_used

DBSession = Annotated[Session, Depends(get_db)]


def require_api_token(
    db: DBSession, authorization: str | None = Header(default=None, alias="Authorization")
) -> ApiToken:
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authorization header")

    token_row = find_token_by_plaintext(db, token)
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api token")

    mark_token_used(db, token_row)
    db.commit()
    db.refresh(token_row)
    return token_row


def require_admin_secret(
    x_oak_eval_admin_token: str | None = Header(default=None, alias="X-Oak-Eval-Admin-Token"),
) -> None:
    import os

    expected = os.getenv("OAK_EVAL_BOOTSTRAP_TOKEN", "dev-bootstrap")
    if x_oak_eval_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")
