import asyncio
import base64
import hashlib
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Interest, User
from app.schemas.user import UserRegisterRequest, UserResponse

router = APIRouter()
PASSWORD_HASH_ITERATIONS = 600_000


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_key = base64.b64encode(derived_key).decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${encoded_salt}${encoded_key}"


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    registration: UserRegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    interest_names = list(dict.fromkeys(registration.interests))

    async with session.begin():
        existing_user = await session.scalar(
            select(User).where(User.email == str(registration.email))
        )
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )

        interests_by_name = {
            interest.name: interest
            for interest in await session.scalars(
                select(Interest).where(Interest.name.in_(interest_names))
            )
        }
        for interest_name in interest_names:
            if interest_name not in interests_by_name:
                interest = Interest(name=interest_name)
                session.add(interest)
                interests_by_name[interest_name] = interest

        user = User(
            email=str(registration.email),
            hashed_password=await asyncio.to_thread(
                _hash_password,
                registration.password,
            ),
            name=registration.name,
            interests=[interests_by_name[name] for name in interest_names],
        )
        session.add(user)
        await session.flush()

    return UserResponse.model_validate(user)
