"""
brain.py — LLM interface for Deepak AI Agent
Supports optional system_prompt so agent.py can pass structured instructions.
"""

import os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama3-70b-8192")

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY environment variable is not set")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client

DEFAULT_SYSTEM = "You are Deepak's autonomous AI assistant. Think clearly and respond usefully."

def think(prompt: str, system_prompt: str = None) -> str:
    """Send prompt to Groq LLM and return text response."""
    client = _get_client()
    messages = [
        {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
        {"role": "user",   "content": prompt},
    ]
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )
    return response.choices[0].message.content
