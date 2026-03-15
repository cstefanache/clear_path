import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gene import Gene
from app.models.project import Project
from app.models.user import User
from app.routes.deps import get_current_user
from app.schemas.benchmark import BenchmarkRequest, BenchmarkResponse
from app.services.benchmark import BenchmarkService, BenchmarkError
from app.services.optimization import gene_record_to_dict

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_project_or_404(project_id: int, user: User, db: Session) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("/{project_id}/benchmark", response_model=BenchmarkResponse)
def run_benchmark(
    project_id: int,
    request: BenchmarkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute the project's fitness function with the provided gene values.

    Returns objective function values and any constraint violations.
    """
    project = _get_project_or_404(project_id, user, db)

    if not project.fitness_function_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fitness function has not been generated yet. Save the definition first.",
        )

    gene_rows = (
        db.query(Gene)
        .filter(Gene.project_id == project_id)
        .order_by(Gene.order)
        .all()
    )

    if not gene_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No genes found for this project. Save the definition first.",
        )

    genes = [gene_record_to_dict(g) for g in gene_rows]

    try:
        result = BenchmarkService.run_benchmark(
            fitness_code=project.fitness_function_code,
            gene_values=request.gene_values,
            genes=genes,
        )
    except BenchmarkError as exc:
        logger.warning("Benchmark failed for project %d: %s", project_id, exc)
        return BenchmarkResponse(results={}, errors=[str(exc)])
    except Exception as exc:
        logger.error("Unexpected benchmark error for project %d: %s", project_id, exc, exc_info=True)
        return BenchmarkResponse(results={}, errors=[f"Unexpected error: {exc}"])

    errors = None
    constraint_violations = result.pop("constraint_violations", None)
    if constraint_violations:
        errors = [str(v) for v in constraint_violations]

    results = result.get("objective_values", {})
    results["fitness"] = result.get("fitness", 0)

    return BenchmarkResponse(results=results, errors=errors)
