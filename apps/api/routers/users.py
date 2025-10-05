from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db import get_async_db
from apps.api.db.models import User, UserToken
from apps.api.security import build_token_prefix, generate_token, hash_token

router = APIRouter()


class UserTokenResponse(BaseModel):
    id: int
    user_id: int
    name: str
    token_prefix: str
    revoked: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserTokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class UserTokenCreateResponse(UserTokenResponse):
    token: str


async def _get_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def _get_user_token(db: AsyncSession, user_id: int, token_id: int) -> UserToken:
    result = await db.execute(
        select(UserToken).where(UserToken.id == token_id, UserToken.user_id == user_id)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    return token


@router.get("/{user_id}/tokens", response_model=List[UserTokenResponse])
async def list_user_tokens(
    user_id: int,
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_async_db),
):
    await _get_user(db, user_id)

    query = select(UserToken).where(UserToken.user_id == user_id)
    if not include_revoked:
        query = query.where(UserToken.revoked.is_(False))

    query = query.order_by(UserToken.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{user_id}/tokens/{token_id}", response_model=UserTokenResponse)
async def get_user_token(
    user_id: int,
    token_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    await _get_user(db, user_id)
    token = await _get_user_token(db, user_id, token_id)
    return token


@router.post(
    "/{user_id}/tokens",
    response_model=UserTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_token(
    user_id: int,
    payload: UserTokenCreateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    await _get_user(db, user_id)

    query = select(UserToken).where(
        UserToken.user_id == user_id,
        UserToken.name == payload.name,
        UserToken.revoked.is_(False),
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token name already in use",
        )

    raw_token = generate_token()
    token = UserToken(
        user_id=user_id,
        name=payload.name,
        token_hash=hash_token(raw_token),
        token_prefix=build_token_prefix(raw_token),
        revoked=False,
    )
    db.add(token)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create token") from exc

    await db.refresh(token)
    token_payload = UserTokenResponse.model_validate(token).model_dump()
    return UserTokenCreateResponse(**token_payload, token=raw_token)


@router.delete("/{user_id}/tokens/{token_id}", response_model=UserTokenResponse)
async def revoke_user_token(
    user_id: int,
    token_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    await _get_user(db, user_id)
    token = await _get_user_token(db, user_id, token_id)

    if token.revoked:
        return token

    token.revoked = True
    token.last_used_at = datetime.utcnow()
    await db.commit()
    await db.refresh(token)
    return token
