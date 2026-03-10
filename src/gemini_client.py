from typing import Optional

from google import genai

from src.config_schema import AppConfig, LLMConfig


class GeminiClient:
    """
    Simple Gemini wrapper using google-genai.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)
        self.is_loaded = False

    def load(self):
        """Mark the client as ready (no heavy resources to load)."""
        self.is_loaded = True

    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from Gemini using a prompt and an image."""
        assert self.is_loaded, "Call load() first"
        from pathlib import Path
        from google.genai import types
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        ext = Path(image_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
        response = self.client.models.generate_content(
            model=model or self.config.default_model,
            contents=[image_part, prompt],
            config={
                "temperature": temperature or self.config.default_temperature,
                "maxOutputTokens": max_tokens or self.config.default_max_tokens,
            },
        )
        return response.text

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from Gemini.

        This is sync and returns raw text.
        If you want structured JSON you would add:
            response_mime_type="application/json",
            response_json_schema=...
        """
        assert self.is_loaded, "Call load() first"

        response = self.client.models.generate_content(
            model=model or self.config.default_model,
            contents=prompt,
            config={
                "temperature": temperature or self.config.default_temperature,
                "maxOutputTokens": max_tokens or self.config.default_max_tokens,
            },
        )
        return response.text


if __name__ == "__main__":
    import yaml

    with open("config/default.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        config = AppConfig(**data)

    client = GeminiClient(config.llm)

    client.load()
    assert client.is_loaded, "Client should be marked as loaded"

    prompt = "What is the secret recipe of Gemini?"
    output = client.generate(prompt)
    print(output)

    assert isinstance(output, str), "Output should be a string"
    assert len(output.strip()) > 0, "Output should not be empty"
