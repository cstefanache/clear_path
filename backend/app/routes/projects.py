import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gene import Gene
from app.models.project import Project
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routes.deps import get_current_user
from app.schemas.project import GeneResponse, ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.llm import LLMService
from app.services.optimization import sync_genes

router = APIRouter()
logger = logging.getLogger(__name__)

_DEFINITION_FIELDS = frozenset(
    ["genes_description", "objectives_description", "constraints_description"]
)


def _get_project_or_404(
    project_id: int, user: User, db: Session
) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def _get_llm_service_optional(user: User, db: Session) -> LLMService | None:
    """Build an LLMService from user settings, returning None if not configured."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
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
    try:
        return LLMService(
            provider=provider,
            api_key=api_key or "",
            model=user_settings.active_model or "",
            base_url=base_url,
        )
    except Exception:
        return None


@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all projects belonging to the current user."""
    return (
        db.query(Project)
        .filter(Project.user_id == user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new optimization project."""
    project = Project(
        user_id=user.id,
        name=project_in.name,
        description=project_in.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get project details. Verifies the caller owns the project."""
    return _get_project_or_404(project_id, user, db)


@router.get("/{project_id}/genes", response_model=List[GeneResponse])
def get_genes(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the parsed gene definitions for a project."""
    _get_project_or_404(project_id, user, db)
    return (
        db.query(Gene)
        .filter(Gene.project_id == project_id)
        .order_by(Gene.order)
        .all()
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update editable project fields.

    When genes_description changes the genes table is repopulated.
    When any definition field changes the fitness function is regenerated.
    """
    project = _get_project_or_404(project_id, user, db)
    update_data = project_in.model_dump(exclude_unset=True)

    genes_changed = "genes_description" in update_data
    definitions_changed = any(k in update_data for k in _DEFINITION_FIELDS)

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    # Build LLM once — used for gene inference fallback and fitness regeneration.
    llm = _get_llm_service_optional(user, db) if (genes_changed or definitions_changed) else None

    # Sync the genes table whenever genes_description was touched (LLM fallback for free-form text).
    if genes_changed:
        await sync_genes(project.id, project.genes_description or "", db, llm=llm)

    # Regenerate the fitness function when any definition changes.
    if definitions_changed and project.genes_description and project.objectives_description:
        if llm:
            try:
                fitness_code = await llm.generate_fitness_function(
                    genes_description=project.genes_description,
                    objectives_description=project.objectives_description,
                    constraints_description=project.constraints_description or "",
                )
                project.fitness_function_code = fitness_code
                db.commit()
                db.refresh(project)
            except Exception as exc:
                logger.error(
                    "Fitness function generation failed for project %d: %s",
                    project_id, exc,
                )

    return project


@router.post("/{project_id}/regenerate-fitness", response_model=ProjectResponse)
async def regenerate_fitness(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate the fitness function from the current definitions using the LLM."""
    project = _get_project_or_404(project_id, user, db)

    if not project.genes_description or not project.objectives_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Genes and objectives descriptions are required to generate a fitness function.",
        )

    llm = _get_llm_service_optional(user, db)
    if not llm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM provider not configured. Please update your settings first.",
        )

    try:
        fitness_code = await llm.generate_fitness_function(
            genes_description=project.genes_description,
            objectives_description=project.objectives_description,
            constraints_description=project.constraints_description or "",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fitness function generation failed: {exc}",
        )

    project.fitness_function_code = fitness_code
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a project and all related data (messages, executions, genes)."""
    project = _get_project_or_404(project_id, user, db)
    db.delete(project)
    db.commit()
