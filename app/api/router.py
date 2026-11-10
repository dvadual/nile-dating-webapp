from fastapi import APIRouter

from app.api.endpoints import users_router

router = APIRouter()
router.include_router(users_router, prefix="/users", tags=["users"])


@router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
