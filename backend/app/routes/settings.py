from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routes.deps import get_current_user
from app.schemas.settings import UserSettingsUpdate, UserSettingsResponse

router = APIRouter()


def _get_or_create_settings(user: User, db: Session) -> UserSettings:
    """Return the user's settings row, creating one if it does not exist."""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/", response_model=UserSettingsResponse)
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's LLM settings. API keys are masked (only last 4 chars shown)."""
    return _get_or_create_settings(user, db)


@router.put("/", response_model=UserSettingsResponse)
def update_settings(
    settings_in: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's LLM provider settings and API keys."""
    settings = _get_or_create_settings(user, db)
    update_data = settings_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
