import re
from functools import lru_cache

from openai import AsyncOpenAI

from backend.core.config import get_settings


class StubLLMClient:
    async def complete(self, prompt: str) -> str:
        return ""

    async def complete_with_image(self, prompt: str, screenshot_data_url: str, model: str | None = None) -> str:
        return ""


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: int):
        self.model = model
        self.client = AsyncOpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout_seconds,
        )

    async def complete(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def complete_with_image(self, prompt: str, screenshot_data_url: str, model: str | None = None) -> str:
        vision_model = model or getattr(get_settings(), "llm_vision_model", "")
        if not vision_model:
            raise ValueError("Vision model is not configured")
        if len(screenshot_data_url) > 2800000 or not re.fullmatch(
            r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}", screenshot_data_url
        ):
            raise ValueError("Vision requires a validated image data URL")
        response = await self.client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": screenshot_data_url}},
                    ],
                }
            ],
        )
        return response.choices[0].message.content


@lru_cache
def _cached_client(base_url: str, api_key: str, model: str, timeout_seconds: int):
    return OpenAICompatibleClient(base_url, api_key, model, timeout_seconds)


def get_llm_client():
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
        return StubLLMClient()
    return _cached_client(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
        settings.llm_timeout_seconds,
    )
