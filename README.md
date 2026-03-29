# Customer Service Backend Skeleton

## What Is Included
- FastAPI app scaffold with route -> service -> repository layering
- Centralized Pydantic settings with env separation (dev, staging, prod)
- SQLAlchemy + PostgreSQL wiring
- Alembic migrations with initial `users` table
- JWT authentication utilities
- Guest mode endpoint: `POST /api/v1/auth/guest`
- Guest-to-registered conversion endpoint: `POST /api/v1/auth/guest/convert`
- Custom `AppError` hierarchy and global exception handlers
- Environment-aware CORS, logging, cookie, and error detail behavior
- Pytest unit and integration test skeletons

## Run Locally
1. Create and activate a Python 3.11+ environment.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Copy env template:
   - `cp .env.example .env`
4. Run migrations:
   - `alembic upgrade head`
5. Start server:
   - `uvicorn app.main:app --reload`

## Environment Separation
Environment-specific behavior is centralized in `app/core/settings.py`:
- `APP_ENV` controls whether runtime is `dev`, `staging`, or `prod`.
- Settings are loaded from `.env` and `.env.<APP_ENV>`.
- Business logic in services/repositories is environment-agnostic.
- Environment differences are isolated in:
  - Config values (e.g., `DATABASE_URL`, `CORS_ORIGINS`)
  - Security defaults (cookie `secure` and `samesite`)
  - Error response detail exposure (detailed only in dev)
  - Logging level

This keeps domain logic stable while allowing safe runtime policy changes per environment.

## API Endpoints (Current Skeleton)
- `POST /api/v1/auth/guest`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/guest/convert`
- `GET /api/v1/auth/session`
- `GET /api/v1/account/me`
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/orders/{order_id}/timeline-sim`
- `GET /health`
