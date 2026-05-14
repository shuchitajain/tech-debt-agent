"""
client.py — Multi-provider LLM wrapper (Groq primary, Gemini fallback)

Supports:
- Groq (FREE, very fast) — set GROQ_API_KEY
- Gemini (FREE tier) — set GOOGLE_API_KEY

The client auto-detects which API key is available.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

# Load .env from project root
_project_root = Path(__file__).parent.parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path)


# Default models
GROQ_MODEL = "llama-3.1-8b-instant" 
GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_TOKENS = 2048


def _get_provider() -> str:
    """Detect which provider to use based on available API keys."""
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    elif os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return "none"


def is_configured() -> bool:
    """Check if any LLM API key is set."""
    return _get_provider() != "none"


def _call_groq(system: str, user: str, max_tokens: int, temperature: float) -> str:
    """Make request to Groq API."""
    from groq import Groq
    
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    return response.choices[0].message.content


def _call_gemini(system: str, user: str, max_tokens: int, temperature: float) -> str:
    """Make request to Gemini API."""
    from google import genai
    
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    full_prompt = f"{system}\n\n---\n\n{user}"
    
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config={"max_output_tokens": max_tokens, "temperature": temperature}
    )
    return response.text


def chat_completion(
    system: str,
    user: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.3,
    **kwargs,  # Ignore unused params like 'model'
) -> str:
    """
    Make a chat completion request to the configured LLM.
    
    Auto-detects provider based on available API key:
    - GROQ_API_KEY → Groq (primary)
    - GOOGLE_API_KEY → Gemini (fallback)
    """
    provider = _get_provider()
    console = Console()
    
    if provider == "none":
        raise EnvironmentError(
            "No LLM API key configured.\n"
            "Set one of:\n"
            "  GROQ_API_KEY=... (get free at https://console.groq.com)\n"
            "  GOOGLE_API_KEY=... (get free at https://aistudio.google.com/apikey)"
        )
    
    try:
        if provider == "groq":
            return _call_groq(system, user, max_tokens, temperature)
        else:
            return _call_gemini(system, user, max_tokens, temperature)
    
    except Exception as e:
        console.print(f"[red]{provider.upper()} API error: {e}[/red]")
        raise


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    console = Console()
    
    console.print("[bold]Testing LLM client...[/bold]\n")
    
    provider = _get_provider()
    if provider == "none":
        console.print("[red]❌ No API key set![/red]")
        console.print("Set GROQ_API_KEY or GOOGLE_API_KEY in .env")
    else:
        console.print(f"[green]✅ Using {provider.upper()}[/green]\n")
        
        console.print("Sending test message...")
        response = chat_completion(
            system="You are a helpful assistant.",
            user="Say 'Hello, tech-debt-finder!' in exactly those words.",
        )
        console.print(f"Response: [cyan]{response}[/cyan]")
