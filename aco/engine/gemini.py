"""Gemini API client wrapper with structured output support."""

import json
import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from aco.engine.models import ExperimentUnderstanding


T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Client for interacting with Google's Gemini API."""
    
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-3-pro-preview",
    ):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var)
            model_name: Model to use for generation
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY or GEMINI_API_KEY "
                "environment variable or pass api_key parameter."
            )
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
    
    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        """
        Generate text from a prompt.
        
        Args:
            prompt: The input prompt
            system_instruction: Optional system instruction
            temperature: Sampling temperature
            max_output_tokens: Maximum output length
        
        Returns:
            Generated text
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        
        return response.text
    
    def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int = 8192,
    ) -> T:
        """
        Generate structured output conforming to a Pydantic model.
        
        Args:
            prompt: The input prompt
            response_schema: Pydantic model class for the response
            system_instruction: Optional system instruction
            temperature: Sampling temperature (lower for structured output)
            max_output_tokens: Maximum output length
        
        Returns:
            Instance of response_schema populated with generated data
        """
        # Build JSON schema from Pydantic model
        schema = response_schema.model_json_schema()
        
        # Create enhanced prompt requesting JSON output
        schema_prompt = f"""
{prompt}

You must respond with valid JSON that conforms to this schema:
```json
{json.dumps(schema, indent=2)}
```

Respond ONLY with the JSON object, no additional text or markdown formatting.
"""
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
            response_mime_type="application/json",
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=schema_prompt,
            config=config,
        )
        
        # Parse the JSON response
        try:
            # Clean up response text (remove markdown code blocks if present)
            text = response.text.strip()
            if text.startswith("```"):
                # Remove markdown code blocks
                lines = text.split("\n")
                # Remove first line (```json) and last line (```)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            
            data = json.loads(text)
            return response_schema.model_validate(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response.text}")
    
    async def generate_async(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        """Async version of generate."""
        import asyncio
        
        return await asyncio.to_thread(
            self.generate,
            prompt,
            system_instruction,
            temperature,
            max_output_tokens,
        )
    
    async def generate_structured_async(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int = 8192,
    ) -> T:
        """Async version of generate_structured."""
        import asyncio
        
        return await asyncio.to_thread(
            self.generate_structured,
            prompt,
            response_schema,
            system_instruction,
            temperature,
            max_output_tokens,
        )


# Singleton instance
_client: GeminiClient | None = None


def get_gemini_client(
    api_key: str | None = None,
    model_name: str = "gemini-3-pro-preview",
) -> GeminiClient:
    """Get or create the Gemini client singleton."""
    global _client
    
    if _client is None:
        _client = GeminiClient(api_key=api_key, model_name=model_name)
    
    return _client


def reset_client() -> None:
    """Reset the client singleton (useful for testing)."""
    global _client
    _client = None
