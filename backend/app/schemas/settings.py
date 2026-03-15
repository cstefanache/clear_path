from typing import Optional

from pydantic import BaseModel


class UserSettingsUpdate(BaseModel):
    active_provider: Optional[str] = None
    active_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_url: Optional[str] = None


class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    active_provider: Optional[str] = None
    active_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_url: Optional[str] = None

    model_config = {"from_attributes": True}

    @staticmethod
    def _mask_key(key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        if len(key) <= 8:
            return "****"
        return key[:4] + "****" + key[-4:]

    def model_post_init(self, __context: object) -> None:
        self.openai_api_key = self._mask_key(self.openai_api_key)
        self.anthropic_api_key = self._mask_key(self.anthropic_api_key)
        self.gemini_api_key = self._mask_key(self.gemini_api_key)
