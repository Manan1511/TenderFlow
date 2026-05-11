"""
core/ollama_client.py

Handles all communication with the local Ollama instance.
Provides a health check and the main analysis generation call.
"""

from __future__ import annotations

import requests

from core.utils import parse_strict_json

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = "gemma4:e4b"
REQUEST_TIMEOUT_SECONDS = 300
HEALTH_CHECK_TIMEOUT_SECONDS = 5

# Maximum characters of parsed PDF text to send to the model.
# Prevents context-window overflow (OOM) which manifests as Ollama 500 errors.
# ~8 000 chars ≈ ~2 000 tokens — safe for gemma4:e4b's 8k context window.
MAX_PROMPT_CHARS = 8_000

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a strict data extraction engine. Your ONLY task is to extract specific
information from government tender documents and return it as a single, valid JSON object.

You MUST follow these rules without exception:
1. Respond with ONLY a JSON object. No explanations, no markdown, no code fences.
2. Do not add any text before or after the JSON object.
3. Every key listed below MUST be present in your response.
4. If information for a key cannot be found, use an empty string "" for string fields
   and an empty array [] for array fields.

Required JSON schema:
{
  "emd_fee": "<string: Earnest Money Deposit amount with currency, e.g. 'INR 50,000'>",
  "processing_fee": "<string: Tender processing/document fee with currency>",
  "manufacturer_documents": ["<string: each required document from the manufacturer>"],
  "bidder_documents": ["<string: each required document the bidder must submit>"],
  "product_supply_requirements": ["<string: each product, quantity, specification to be supplied>"],
  "email_draft": "<string: a professional email to the manufacturer requesting the listed manufacturer documents>"
}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_ollama_connection() -> bool:
    """
    Verify that the local Ollama server is running and reachable.

    Returns:
        True  if the server responds with HTTP 200.
        False if the connection fails for any reason.
    """
    try:
        response = requests.get(
            OLLAMA_BASE_URL,
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def _truncate_text(text: str) -> tuple[str, bool]:
    """
    Truncate *text* to MAX_PROMPT_CHARS to stay within the model context window.

    Returns:
        (text, was_truncated) — The (possibly shortened) text and a flag.
    """
    if len(text) <= MAX_PROMPT_CHARS:
        return text, False
    # Preserve the start (cover page, fees) and end (schedules) of the doc
    half = MAX_PROMPT_CHARS // 2
    truncated = (
        text[:half]
        + "\n\n[... middle section omitted for brevity ...]\n\n"
        + text[-half:]
    )
    return truncated, True


def generate_analysis(parsed_text: str) -> dict:
    """
    Send the parsed tender text to the local Ollama model and return a
    validated dict of extracted requirements.

    Args:
        parsed_text: Combined text + table content from the PDF parser.

    Returns:
        A dict with the keys defined in REQUIRED_JSON_KEYS (see utils.py).

    Raises:
        ConnectionError: If Ollama is unreachable or returns a server error.
        requests.Timeout: If the request exceeds REQUEST_TIMEOUT_SECONDS.
        ValueError: If the response JSON is malformed or incomplete.
    """
    safe_text, was_truncated = _truncate_text(parsed_text)

    payload = {
        "model": MODEL_NAME,
        "system": _SYSTEM_PROMPT,
        "prompt": (
            "Extract the required information from the following tender document "
            "and return ONLY the JSON object as instructed.\n\n"
            f"TENDER DOCUMENT:\n{safe_text}"
        ),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 2048,  # Capped — a valid JSON response fits in <1k tokens
        },
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError as exc:
        raise ConnectionError(
            "Cannot reach Ollama at localhost:11434. "
            "Make sure Ollama is running."
        ) from exc
    except requests.Timeout as exc:
        raise requests.Timeout(
            f"Ollama did not respond within {REQUEST_TIMEOUT_SECONDS}s. "
            "The model may still be loading — try again in a moment."
        ) from exc

    # Translate HTTP errors into clear, actionable messages
    if response.status_code == 500:
        # Most common cause: model name wrong, OOM, or model not pulled
        raise ConnectionError(
            f"Ollama returned a 500 Internal Server Error.\n\n"
            f"Likely causes:\n"
            f"  • Model '{MODEL_NAME}' is not pulled — run: ollama pull {MODEL_NAME}\n"
            f"  • Ollama ran out of memory processing this document\n"
            f"  • The model crashed — restart Ollama and try again"
        )
    if response.status_code == 404:
        raise ConnectionError(
            f"Model '{MODEL_NAME}' was not found on this Ollama instance.\n"
            f"Pull it first:  ollama pull {MODEL_NAME}"
        )

    response.raise_for_status()

    response_data: dict = response.json()
    raw_text: str = response_data.get("response", "")

    if not raw_text.strip():
        raise ValueError(
            "Ollama returned an empty response. "
            "The model may have timed out internally. Please try again."
        )

    return parse_strict_json(raw_text)
