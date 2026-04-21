from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import DBSession, require_admin_secret
from app.schemas.remote import TokenCreate, TokenCreated
from app.services.remote import create_api_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/tokens", response_model=TokenCreated, dependencies=[Depends(require_admin_secret)])
def create_token(payload: TokenCreate, db: DBSession) -> TokenCreated:
    token_row, token = create_api_token(db, name=payload.name)
    db.commit()
    return TokenCreated(token_id=token_row.id, name=token_row.name, token_prefix=token_row.token_prefix, token=token)
