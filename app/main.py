import asyncio
import base64
import hashlib
import logging
import os
import secrets
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.router import router as api_router
from app.core.database import DATABASE_URL, engine, get_db
from app.models import Interest, User

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"
SEED_API_KEY = os.getenv("SEED_API_KEY")
PASSWORD_HASH_ITERATIONS = 600_000
SAMPLE_USERS = (
    ("alex@example.edu", "Alex", ("Python", "Music")),
    ("jordan@example.edu", "Jordan", ("Art", "Basketball")),
    ("casey@example.edu", "Casey", ("Python", "Art")),
)
SAMPLE_INTERESTS = ("Python", "Art", "Music", "Basketball")
MIGRATION_LOCK_ID = 5_841_930_276_415_802_101
SEED_LOCK_ID = 5_841_930_276_415_802_102


def _ensure_alembic_files() -> None:
    missing_ini = not ALEMBIC_INI.is_file()
    missing_dir = not ALEMBIC_DIR.is_dir()
    missing_env = not (ALEMBIC_DIR / "env.py").is_file()
    missing_template = not (ALEMBIC_DIR / "script.py.mako").is_file()
    if not (missing_ini or missing_dir or missing_env or missing_template):
        return

    with tempfile.TemporaryDirectory(prefix="alembic-bootstrap-") as temp_dir:
        temporary_root = Path(temp_dir)
        temporary_ini = temporary_root / "alembic.ini"
        temporary_alembic = temporary_root / "alembic"
        command.init(
            Config(str(temporary_ini)),
            str(temporary_alembic),
            template="async",
            package=False,
        )

        if missing_ini:
            ini_contents = temporary_ini.read_text(encoding="utf-8")
            ini_contents = "\n".join(
                "script_location = %(here)s/alembic"
                if line.startswith("script_location =")
                else "sqlalchemy.url ="
                if line.startswith("sqlalchemy.url =")
                else line
                for line in ini_contents.splitlines()
            )
            ALEMBIC_INI.write_text(ini_contents + "\n", encoding="utf-8")

        ALEMBIC_DIR.mkdir(parents=True, exist_ok=True)
        for filename, missing in (
            ("env.py", missing_env),
            ("script.py.mako", missing_template),
        ):
            if not missing:
                continue
            generated_file = temporary_alembic / filename
            contents = generated_file.read_text(encoding="utf-8")
            if filename == "env.py":
                marker = "target_metadata = None"
                replacement = (
                    "from importlib import import_module\n"
                    "from app.core.database import Base\n"
                    "\n"
                    "import_module(\"app.models\")\n"
                    "target_metadata = Base.metadata"
                )
                if marker not in contents:
                    raise RuntimeError(
                        "The generated Alembic environment has no metadata marker."
                    )
                contents = contents.replace(marker, replacement, 1)
            (ALEMBIC_DIR / filename).write_text(contents, encoding="utf-8")

    (ALEMBIC_DIR / "versions").mkdir(parents=True, exist_ok=True)


def _run_migrations() -> None:
    _ensure_alembic_files()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    config.set_main_option(
        "sqlalchemy.url",
        DATABASE_URL.render_as_string(hide_password=False).replace("%", "%%"),
    )

    version_dir = ALEMBIC_DIR / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    if not any(
        path.suffix == ".py" and path.name != "__init__.py"
        for path in version_dir.iterdir()
    ):
        logger.info("No Alembic revisions found; generating the initial revision.")
        command.revision(config, message="initial schema", autogenerate=True)

    logger.info("Applying Alembic migrations.")
    command.upgrade(config, "head")


def _hash_unusable_password() -> str:
    salt = secrets.token_bytes(16)
    password = secrets.token_bytes(32)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password,
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_key = base64.b64encode(derived_key).decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${encoded_salt}${encoded_key}"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    try:
        async with engine.connect() as lock_connection:
            await lock_connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            await lock_connection.commit()
            logger.info("Acquired PostgreSQL migration lock.")
            migration_task = asyncio.create_task(asyncio.to_thread(_run_migrations))
            try:
                await asyncio.shield(migration_task)
            except asyncio.CancelledError:
                await migration_task
                raise
            finally:
                await lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
                await lock_connection.commit()
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Campus Dating API",
    description="API for a campus-focused dating app MVP.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")


@app.post("/seed-data", tags=["development"])
async def seed_data(
    session: Annotated[AsyncSession, Depends(get_db)],
    provided_key: Annotated[str | None, Header(alias="X-Seed-API-Key")] = None,
) -> dict[str, int]:
    if not SEED_API_KEY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if provided_key is None or not secrets.compare_digest(provided_key, SEED_API_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    users_created = 0
    interests_created = 0
    associations_added = 0

    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": SEED_LOCK_ID},
        )
        interest_result = await session.scalars(
            select(Interest).where(Interest.name.in_(SAMPLE_INTERESTS))
        )
        interests_by_name = {interest.name: interest for interest in interest_result}
        for name in SAMPLE_INTERESTS:
            if name not in interests_by_name:
                interest = Interest(name=name)
                session.add(interest)
                interests_by_name[name] = interest
                interests_created += 1
        await session.flush()

        sample_emails = [email for email, _, _ in SAMPLE_USERS]
        user_result = await session.scalars(
            select(User)
            .options(selectinload(User.interests))
            .where(User.email.in_(sample_emails))
        )
        users_by_email = {user.email: user for user in user_result}

        for email, name, interest_names in SAMPLE_USERS:
            user = users_by_email.get(email)
            if user is None:
                user = User(
                    email=email,
                    hashed_password=await asyncio.to_thread(_hash_unusable_password),
                    name=name,
                )
                session.add(user)
                users_by_email[email] = user
                users_created += 1

            for interest_name in interest_names:
                interest = interests_by_name[interest_name]
                if interest not in user.interests:
                    user.interests.append(interest)
                    associations_added += 1

    return {
        "users_created": users_created,
        "interests_created": interests_created,
        "associations_added": associations_added,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)