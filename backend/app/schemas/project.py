from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genes_description: Optional[str] = None
    objectives_description: Optional[str] = None
    constraints_description: Optional[str] = None
    fitness_function_code: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    genes_description: Optional[str] = None
    objectives_description: Optional[str] = None
    constraints_description: Optional[str] = None
    fitness_function_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GeneResponse(BaseModel):
    id: int
    project_id: int
    name: str
    type: str
    low: Optional[float] = None
    high: Optional[float] = None
    decimals: Optional[int] = None
    options: Optional[str] = None
    description: Optional[str] = None
    order: int

    model_config = {"from_attributes": True}
