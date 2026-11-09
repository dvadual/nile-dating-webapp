# nile-dating-webapp
trying to create a dating site curated for students at my uni personal project to practice and showcase web development skills 

## Backend

Install the Python dependencies with `pip install -r requirements.txt`. Set
`DATABASE_URL` to a PostgreSQL connection URL before starting the API; local
development defaults to `postgresql+asyncpg://postgres:postgres@localhost:5432/nile_dating`.
Set `APP_ENV=production` to require an explicit database URL. The API applies
Alembic migrations during startup. The optional `POST /seed-data` endpoint is
disabled unless `SEED_API_KEY` is configured; provide that key in the
`X-Seed-API-Key` header to seed sample users and interests.

Run locally with `python -m app.main`; the API listens on port 8000.
