import json
import logging
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat import ChatMessage, MessageRole
from app.models.project import Project
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routes.deps import get_current_user
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatResponse
from app.services.llm import LLMService
from app.services.optimization import sync_genes

router = APIRouter()
logger = logging.getLogger(__name__)

# Fields we extract from the AI-generated JSON to auto-update the project.
_PROJECT_FIELDS = frozenset(
    ["genes_description", "objectives_description", "constraints_description"]
)


def _get_project_or_404(project_id: int, user: User, db: Session) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_llm_service(user: User, db: Session) -> LLMService:
    """Build an LLMService from the user's saved settings."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not user_settings or not user_settings.active_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM provider not configured. Please update your settings first.",
        )

    provider = user_settings.active_provider.lower()
    api_key_map = {
        "openai": user_settings.openai_api_key,
        "anthropic": user_settings.anthropic_api_key,
        "gemini": user_settings.gemini_api_key,
    }

    api_key = api_key_map.get(provider, "")
    if provider != "ollama" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key for provider '{provider}' is not set. Please update your settings.",
        )

    base_url = user_settings.ollama_url if provider == "ollama" else None
    return LLMService(
        provider=provider,
        api_key=api_key or "",
        model=user_settings.active_model or "",
        base_url=base_url,
    )


def _build_context_message(project: Project) -> str:
    """Build a context summary of the current project state to prepend to the conversation."""
    parts: list[str] = [
        f"[Current project definitions — name: {project.name}]",
        "These are the current definitions. Update them based on the user's request. "
        "Always output the COMPLETE definitions (not diffs) in the JSON block.",
    ]
    if project.description:
        parts.append(f"Project description: {project.description}")
    if project.genes_description:
        parts.append(f"Current Genes Description:\n{project.genes_description}")
    if project.objectives_description:
        parts.append(f"Current Objectives Description:\n{project.objectives_description}")
    if project.constraints_description:
        parts.append(f"Current Constraints Description:\n{project.constraints_description}")
    if not project.genes_description and not project.objectives_description:
        parts.append("No definitions yet — this is a new project.")
    return "\n\n".join(parts)


def _extract_json_updates(text: str) -> dict:
    """Extract project-field updates from a JSON code block in the AI response."""
    pattern = r"```(?:json)?\s*\n(\{.*?\})\s*\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    for raw in matches:
        try:
            data = json.loads(raw)
            updates = {k: v for k, v in data.items() if k in _PROJECT_FIELDS and isinstance(v, str)}
            if updates:
                return updates
        except json.JSONDecodeError:
            continue
    return {}


@router.get("/{project_id}/messages", response_model=List[ChatMessageResponse])
def get_messages(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full chat history for a project."""
    _get_project_or_404(project_id, user, db)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.post("/{project_id}/messages", response_model=ChatResponse)
async def send_message(
    project_id: int,
    message_in: ChatMessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a user message and receive an AI response.

    If the AI response contains a JSON block with definition fields
    (genes_description, objectives_description, constraints_description),
    the project is automatically updated and the fitness function is regenerated.
    """
    project = _get_project_or_404(project_id, user, db)
    llm = _get_llm_service(user, db)

    # Persist the user message.
    user_msg = ChatMessage(
        project_id=project_id,
        role=MessageRole.user,
        content=message_in.content,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Build the message payload for the LLM.
    context_text = _build_context_message(project)

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    llm_messages: list[dict] = []

    if project.genes_description or project.objectives_description or project.constraints_description:
        llm_messages.append({"role": "user", "content": context_text})
        llm_messages.append({"role": "assistant", "content": "Understood, I have the current project context."})

    for msg in history:
        llm_messages.append({"role": msg.role.value, "content": msg.content})

    # Call the LLM for the chat response.
    try:
        assistant_text = await llm.chat(llm_messages, use_cache=False)
    except Exception as exc:
        logger.error("LLM chat call failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )

    # Persist the assistant response.
    assistant_msg = ChatMessage(
        project_id=project_id,
        role=MessageRole.assistant,
        content=assistant_text,
    )
    db.add(assistant_msg)

    # Apply any definition updates from the AI response.
    updates = _extract_json_updates(assistant_text)
    if updates:
        for field, value in updates.items():
            setattr(project, field, value)

    db.commit()
    db.refresh(assistant_msg)
    db.refresh(project)

    # If genes changed, sync the genes table (LLM fallback for free-form text).
    if "genes_description" in updates and project.genes_description:
        await sync_genes(project.id, project.genes_description, db, llm=llm)

    # If any definition changed and we have enough to generate a fitness function, do so.
    if updates and project.genes_description and project.objectives_description:
        try:
            fitness_code = await llm.generate_fitness_function(
                genes_description=project.genes_description,
                objectives_description=project.objectives_description,
                constraints_description=project.constraints_description or "",
            )
            project.fitness_function_code = fitness_code
            db.commit()
        except Exception as exc:
            logger.error("Fitness function generation failed for project %d: %s", project_id, exc)

    return ChatResponse(
        message=ChatMessageResponse.model_validate(assistant_msg),
        genes_description=updates.get("genes_description"),
        objectives_description=updates.get("objectives_description"),
        constraints_description=updates.get("constraints_description"),
    )
