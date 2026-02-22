"""
Chat endpoints for the Gateway API.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import JWTPayload, get_current_user
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatMode,
    SessionInfo,
    SessionListResponse,
)
from app.services.database import DatabaseService, get_database_service
from app.services.inference import InferenceService, get_inference_service


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: JWTPayload = Depends(get_current_user),
    db: DatabaseService = Depends(get_database_service),
    inference: InferenceService = Depends(get_inference_service),
) -> ChatResponse:
    """
    Send a message and get an AI response.
    
    - Creates a new session if session_id is not provided
    - Stores user message and AI response in database
    - Returns the AI response with session info
    """
    user_id = user.user_id
    
    # Get or create session
    if request.session_id:
        session = db.get_session(request.session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    else:
        # Create new session with first message as title hint
        title = request.message[:50] + "..." if len(request.message) > 50 else request.message
        session = db.create_session(user_id, title)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
    
    session_id = session["id"]
    
    # Store user message
    user_msg = db.create_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=request.message,
    )
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store message"
        )
    
    # Get conversation history for context
    history = db.get_session_messages(session_id, user_id, limit=20)
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
    ]
    
    # Generate AI response
    inference_result = await inference.generate_response(
        messages=messages,
        mode=request.mode.value,
    )
    
    # Store assistant response
    assistant_msg = db.create_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=inference_result["content"],
        mode_used=inference_result["mode_used"],
        tokens_used=inference_result.get("tokens_used"),
    )
    if not assistant_msg:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store response"
        )
    
    return ChatResponse(
        session_id=session_id,
        message=ChatMessage(
            id=assistant_msg["id"],
            role="assistant",
            content=assistant_msg["content"],
            mode_used=assistant_msg.get("mode_used"),
            created_at=assistant_msg["created_at"],
        ),
        session_title=session.get("title"),
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: JWTPayload = Depends(get_current_user),
    db: DatabaseService = Depends(get_database_service),
) -> SessionListResponse:
    """List all chat sessions for the current user."""
    sessions = db.list_sessions(user.user_id)
    return SessionListResponse(
        sessions=[
            SessionInfo(
                id=s["id"],
                title=s["title"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                is_archived=s.get("is_archived", False),
            )
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_session_messages(
    session_id: str,
    user: JWTPayload = Depends(get_current_user),
    db: DatabaseService = Depends(get_database_service),
) -> List[ChatMessage]:
    """Get all messages in a session."""
    # Verify session ownership
    session = db.get_session(session_id, user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    messages = db.get_session_messages(session_id, user.user_id)
    return [
        ChatMessage(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            mode_used=m.get("mode_used"),
            created_at=m["created_at"],
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user: JWTPayload = Depends(get_current_user),
    db: DatabaseService = Depends(get_database_service),
):
    """Delete a chat session and all its messages."""
    success = db.delete_session(session_id, user.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
