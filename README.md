# nile-dating-webapp
trying to create a dating site curated for students at my uni personal project to practice and showcase web development skills 

## Backend

Install the Python dependencies with `pip install -r requirements.txt`. The API
loads `DATABASE_URL` from a root `.env` file when present; an environment
variable takes precedence. Local development defaults to `postgresql+asyncpg://postgres:postgres@localhost:5432/nile_dating`.
Set `APP_ENV=production` to require an explicit database URL. The API applies
Alembic migrations during startup. The optional `POST /seed-data` endpoint is
disabled unless `SEED_API_KEY` is configured; provide that key in the
`X-Seed-API-Key` header to seed sample users and interests.

Run locally with `python main.py`; the API listens on port 8000.

User registration is available at `POST /api/users/signup` and is documented
in Swagger UI at `/docs`. Open the `POST /api/users/signup` operation, choose
**Try it out**, enter an email, password, name, and up to ten interest names,
then choose **Execute**. The response never includes the password or its hash.

Install the test dependencies with `pip install -r requirements-dev.txt` and
run the registration tests with `pytest`.
