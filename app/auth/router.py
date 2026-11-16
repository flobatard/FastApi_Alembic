from fastapi import APIRouter

from app.auth.schemas import MeRead
from app.core.auth import CurrentUser

router = APIRouter(tags=["auth"])


@router.get("/me")
async def read_me(user: CurrentUser) -> MeRead:
    """Demo protected route: returns the authenticated user's identity."""
    return MeRead(
        sub=user.sub,
        email=user.email,
        roles=sorted(user.roles),
        claims=user.claims,
    )
