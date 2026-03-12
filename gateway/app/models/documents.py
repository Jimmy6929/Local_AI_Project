"""
Pydantic models for the documents / RAG endpoints.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Metadata about an uploaded document."""
    id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Response for GET /documents."""
    documents: List[DocumentInfo]


class UploadResponse(BaseModel):
    """Response for POST /documents/upload."""
    id: str
    filename: str
    status: str
    chunks: int = 0
    message: str = "Document uploaded and processed"
