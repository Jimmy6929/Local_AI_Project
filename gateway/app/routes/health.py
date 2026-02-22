"""
Health check endpoints for the Gateway API.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.middleware.auth import JWTPayload, get_current_user


router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str = "0.1.0"


class AuthenticatedHealthResponse(HealthResponse):
    """Health check response with user info."""
    user_id: str
    email: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Public health check endpoint.
    Returns 200 if the service is running.
    """
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
    )


@router.get("/health/auth", response_model=AuthenticatedHealthResponse)
async def authenticated_health_check(
    user: JWTPayload = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedHealthResponse:
    """
    Authenticated health check endpoint.
    Returns 200 with user info if valid JWT provided.
    Returns 401 if no token or invalid token.
    """
    return AuthenticatedHealthResponse(
        status="healthy",
        service=settings.app_name,
        user_id=user.user_id,
        email=user.email,
    )
