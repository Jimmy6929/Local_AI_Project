"""
Chat request and response models.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ChatMode(str, Enum):
    """Inference mode for chat."""
    INSTANT = "instant"
    THINKING = "thinking"


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    message: str = Field(..., min_length=1, max_length=32000, description="User message")
    session_id: Optional[str] = Field(None, description="Existing session ID, or null for new session")
    mode: ChatMode = Field(ChatMode.INSTANT, description="Inference mode")


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    mode_used: Optional[str] = None
    created_at: datetime


class ChatResponse(BaseModel):
    """Response body for POST /chat."""
    session_id: str
    message: ChatMessage
    session_title: Optional[str] = None


class SessionInfo(BaseModel):
    """Chat session information."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    is_archived: bool = False


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: List[SessionInfo]
