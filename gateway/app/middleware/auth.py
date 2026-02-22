"""
JWT Authentication middleware for validating Supabase tokens.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import Settings, get_settings


# HTTP Bearer token scheme
security = HTTPBearer()


class JWTPayload(BaseModel):
    """Decoded JWT payload from Supabase."""
    sub: str  # User ID (UUID)
    email: Optional[str] = None
    role: Optional[str] = None
    aud: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    
    @property
    def user_id(self) -> str:
        """Alias for sub (subject) which contains the user ID."""
        return self.sub


def decode_jwt(
    token: str,
    settings: Settings,
) -> JWTPayload:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token string
        settings: Application settings containing JWT secret
        
    Returns:
        JWTPayload with decoded token data
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_aud": False,  # Supabase doesn't always set audience
            }
        )
        return JWTPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> JWTPayload:
    """
    FastAPI dependency to extract and validate the current user from JWT.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: JWTPayload = Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    return decode_jwt(credentials.credentials, settings)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    settings: Settings = Depends(get_settings),
) -> Optional[JWTPayload]:
    """
    FastAPI dependency for optional authentication.
    Returns None if no token provided, validates if token is present.
    """
    if credentials is None:
        return None
    return decode_jwt(credentials.credentials, settings)
