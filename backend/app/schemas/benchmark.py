from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BenchmarkRequest(BaseModel):
    gene_values: Dict[str, Any]


class BenchmarkResponse(BaseModel):
    results: Dict[str, Any]
    errors: Optional[List[str]] = None
