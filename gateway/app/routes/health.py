"""
Health check endpoints for the Gateway API.
"""

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.middleware.auth import JWTPayload, get_current_user
from app.services.inference import InferenceService, get_inference_service


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


class InferenceHealthResponse(BaseModel):
    """Health check response for inference endpoints."""
    instant: Dict[str, Any]
    thinking: Dict[str, Any]


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


@router.get("/health/inference", response_model=InferenceHealthResponse)
async def inference_health_check(
    inference: InferenceService = Depends(get_inference_service),
) -> InferenceHealthResponse:
    """
    Check health of inference endpoints (instant and thinking).
    Public endpoint — no auth required.
    """
    instant_status = await inference.check_health("instant")
    thinking_status = await inference.check_health("thinking")
    
    return InferenceHealthResponse(
        instant=instant_status,
        thinking=thinking_status,
    )
