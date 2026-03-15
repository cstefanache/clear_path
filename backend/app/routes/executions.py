import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routes.deps import get_current_user
from app.schemas.execution import ExecutionCreate, ExecutionResponse
from app.services.llm import LLMService
from app.services.optimization import OptimizationService, OptimizationError

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


def _build_llm_service(user_id: int, db: Session) -> LLMService | None:
    """Attempt to build an LLM service for result interpretation. Returns None if not configured."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not user_settings or not user_settings.active_provider:
        return None

    provider = user_settings.active_provider.lower()
    api_key_map = {
        "openai": user_settings.openai_api_key,
        "anthropic": user_settings.anthropic_api_key,
        "gemini": user_settings.gemini_api_key,
    }
    api_key = api_key_map.get(provider, "")
    if provider != "ollama" and not api_key:
        return None

    base_url = user_settings.ollama_url if provider == "ollama" else None
    return LLMService(
        provider=provider,
        api_key=api_key or "",
        model=user_settings.active_model or "",
        base_url=base_url,
    )


async def _run_optimization_task(
    execution_id: int,
    user_id: int,
    project_id: int,
    fitness_code: str,
    objectives_description: str,
    constraints_description: str,
    genes_description: str,
    num_iterations: int,
) -> None:
    """Background task that runs the genetic algorithm optimization and stores results."""
    db = SessionLocal()
    try:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            logger.error("Execution %d not found when starting background task", execution_id)
            return

        execution.status = ExecutionStatus.running
        db.commit()

        def on_progress(current_generation: int, total_generations: int) -> None:
            """Callback invoked by the optimization service to report progress."""
            pct = int((current_generation / max(total_generations, 1)) * 100)
            db.query(Execution).filter(Execution.id == execution_id).update({"progress": pct})
            db.commit()

        service = OptimizationService()
        try:
            result_data = service.run_optimization(
                fitness_code=fitness_code,
                project_id=project_id,
                db=db,
                num_iterations=num_iterations,
                on_progress=on_progress,
            )
        except OptimizationError as exc:
            logger.error("Optimization failed for execution %d: %s", execution_id, exc)
            execution.status = ExecutionStatus.failed
            execution.result_data = {"error": str(exc)}
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        except Exception as exc:
            logger.error("Optimization failed for execution %d: %s", execution_id, exc, exc_info=True)
            execution.status = ExecutionStatus.failed
            execution.result_data = {"error": str(exc)}
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        execution.status = ExecutionStatus.completed
        execution.progress = 100
        execution.result_data = result_data
        execution.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Attempt AI interpretation of the results.
        try:
            llm = _build_llm_service(user_id, db)
            if llm:
                interpretation_prompt = (
                    "Interpret the following genetic algorithm optimization results "
                    "in the context of the business problem.\n\n"
                    f"Genes:\n{genes_description}\n\n"
                    f"Objectives:\n{objectives_description}\n\n"
                    f"Constraints:\n{constraints_description}\n\n"
                    f"Results:\n{result_data}\n\n"
                    "Provide a clear, business-friendly interpretation of the best solution(s) found. "
                    "Explain what the optimal gene values mean in practical terms and how well "
                    "the objectives were achieved."
                )
                interpretation = await llm.chat([
                    {"role": "user", "content": interpretation_prompt},
                ], use_cache=False)
                execution.interpretation = interpretation
                db.commit()
        except Exception as exc:
            logger.warning("AI interpretation failed for execution %d: %s", execution_id, exc)
            # Non-fatal: the optimization results are still stored.

    except Exception as exc:
        logger.error("Unexpected error in optimization task for execution %d: %s", execution_id, exc, exc_info=True)
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if execution and execution.status not in (ExecutionStatus.completed, ExecutionStatus.failed):
                execution.status = ExecutionStatus.failed
                execution.result_data = {"error": str(exc)}
                execution.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            logger.error("Failed to mark execution %d as failed", execution_id, exc_info=True)
    finally:
        db.close()


@router.post("/{project_id}/executions", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def start_execution(
    project_id: int,
    execution_in: ExecutionCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new optimization execution.

    Creates an Execution record with status=pending and launches the
    genetic algorithm optimization in the background.
    """
    project = _get_project_or_404(project_id, user, db)

    if not project.fitness_function_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fitness function code has not been defined for this project yet.",
        )

    # Verify genes exist in the database
    from app.models.gene import Gene
    gene_count = db.query(Gene).filter(Gene.project_id == project.id).count()
    if not gene_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No gene definitions found for this project. Save the definition first.",
        )

    execution = Execution(
        project_id=project_id,
        num_iterations=execution_in.num_iterations,
        status=ExecutionStatus.pending,
        progress=0,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    background_tasks.add_task(
        _run_optimization_task,
        execution_id=execution.id,
        user_id=user.id,
        project_id=project.id,
        fitness_code=project.fitness_function_code,
        objectives_description=project.objectives_description or "",
        constraints_description=project.constraints_description or "",
        genes_description=project.genes_description or "",
        num_iterations=execution_in.num_iterations,
    )

    return execution


@router.get("/{project_id}/executions", response_model=List[ExecutionResponse])
def list_executions(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all executions for a project, most recent first."""
    _get_project_or_404(project_id, user, db)
    return (
        db.query(Execution)
        .filter(Execution.project_id == project_id)
        .order_by(Execution.created_at.desc())
        .all()
    )


@router.post("/{project_id}/executions/{execution_id}/interpret", response_model=ExecutionResponse)
async def interpret_execution(
    project_id: int,
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) an AI interpretation for a completed execution."""
    project = _get_project_or_404(project_id, user, db)
    execution = (
        db.query(Execution)
        .filter(Execution.id == execution_id, Execution.project_id == project_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if execution.status != ExecutionStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Execution is not completed yet.")

    llm = _build_llm_service(user.id, db)
    if not llm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM provider not configured. Please update your settings first.",
        )

    interpretation_prompt = (
        "Interpret the following genetic algorithm optimization results "
        "in the context of the business problem.\n\n"
        f"Project: {project.name}\n"
        f"Description: {project.description or 'N/A'}\n\n"
        f"Genes:\n{project.genes_description or 'N/A'}\n\n"
        f"Objectives:\n{project.objectives_description or 'N/A'}\n\n"
        f"Constraints:\n{project.constraints_description or 'N/A'}\n\n"
        f"Results:\n{execution.result_data}\n\n"
        "Provide a clear, business-friendly interpretation of the best solution(s) found. "
        "Explain what the optimal gene values mean in practical terms and how well "
        "the objectives were achieved."
    )

    try:
        interpretation = await llm.chat([
            {"role": "user", "content": interpretation_prompt},
        ])
        execution.interpretation = interpretation
        db.commit()
        db.refresh(execution)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI interpretation failed: {exc}",
        )

    return execution


@router.get("/{project_id}/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    project_id: int,
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution details including status, progress, results, and AI interpretation."""
    _get_project_or_404(project_id, user, db)
    execution = (
        db.query(Execution)
        .filter(Execution.id == execution_id, Execution.project_id == project_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.delete("/{project_id}/executions/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution(
    project_id: int,
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an execution."""
    _get_project_or_404(project_id, user, db)
    execution = (
        db.query(Execution)
        .filter(Execution.id == execution_id, Execution.project_id == project_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    db.delete(execution)
    db.commit()
