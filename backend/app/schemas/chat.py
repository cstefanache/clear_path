from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    id: int
    project_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    message: ChatMessageResponse
    genes_description: Optional[str] = None
    objectives_description: Optional[str] = None
    constraints_description: Optional[str] = None
