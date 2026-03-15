from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExecutionCreate(BaseModel):
    num_iterations: int = Field(default=100, ge=1)


class ExecutionResponse(BaseModel):
    id: int
    project_id: int
    num_iterations: int
    status: str
    progress: int
    result_data: Optional[Any] = None
    interpretation: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExecutionProgress(BaseModel):
    id: int
    status: str
    progress: int

    model_config = {"from_attributes": True}
