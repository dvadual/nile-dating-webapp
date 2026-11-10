import base64
import hashlib
import hmac

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.models import Interest, User
from main import app


@pytest_asyncio.fixture
async def database() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(
    database: async_sessionmaker[AsyncSession],
) -> AsyncClient:
    async def override_get_db():
        async with database() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_signup_creates_user_and_interests(
    client: AsyncClient,
    database: async_sessionmaker[AsyncSession],
) -> None:
    async with database() as session:
        session.add(Interest(name="Music"))
        await session.commit()

    response = await client.post(
        "/api/users/signup",
        json={
            "email": "new.student@example.edu",
            "password": "a-secure-password",
            "name": "New Student",
            "interests": ["Music", "Python", "Music"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "new.student@example.edu"
    assert payload["name"] == "New Student"
    assert payload["interests"] == ["Music", "Python"]
    assert "password" not in payload
    assert "hashed_password" not in payload

    async with database() as session:
        user = await session.scalar(
            select(User).where(User.email == "new.student@example.edu")
        )
        assert user is not None
        assert user.hashed_password != "a-secure-password"
        algorithm, iterations, salt, expected_hash = user.hashed_password.split("$")
        assert algorithm == "pbkdf2_sha256"
        assert int(iterations) == 600_000
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            b"a-secure-password",
            base64.b64decode(salt),
            int(iterations),
        )
        assert hmac.compare_digest(base64.b64encode(actual_hash).decode(), expected_hash)

        interests = await session.scalars(select(Interest).order_by(Interest.name))
        assert [interest.name for interest in interests] == ["Music", "Python"]
        assert len(user.interests) == 2


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_email(client: AsyncClient) -> None:
    registration = {
        "email": "duplicate@example.edu",
        "password": "a-secure-password",
        "name": "First Student",
        "interests": [],
    }

    first_response = await client.post("/api/users/signup", json=registration)
    duplicate_response = await client.post(
        "/api/users/signup",
        json={**registration, "name": "Second Student"},
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == (
        "An account with this email already exists."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
    ],
)
async def test_signup_rejects_invalid_registration(
    client: AsyncClient,
    overrides: dict[str, str],
) -> None:
    registration = {
        "email": "valid.student@example.edu",
        "password": "a-secure-password",
        "name": "Valid Student",
        "interests": [],
    }

    response = await client.post(
        "/api/users/signup",
        json={**registration, **overrides},
    )

    assert response.status_code == 422
    assert response.json()["detail"]
