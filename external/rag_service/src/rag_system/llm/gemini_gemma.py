from google import genai
from google.genai import types

class GemmaClient:
    """
    Calls Gemma-3-27B-IT via Gemini API using google-genai SDK.
    """
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.2, max_output_tokens: int = 800) -> str:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens
            ),
        )
        return resp.text or ""
