"""
core/ollama_client.py

Handles all communication with the local Ollama instance.
Provides a health check and the main analysis generation call.
"""

from __future__ import annotations

import json

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


def generate_analysis(parsed_text: str) -> dict:
    """
    Send the parsed tender text to the local Ollama model and return a
    validated dict of extracted requirements.

    Args:
        parsed_text: Combined text + table content from the PDF parser.

    Returns:
        A dict with the keys defined in REQUIRED_JSON_KEYS (see utils.py).

    Raises:
        requests.ConnectionError:  If Ollama is not reachable.
        requests.Timeout:          If the request exceeds REQUEST_TIMEOUT_SECONDS.
        requests.RequestException: For any other HTTP-level error.
        ValueError:                If the response JSON is malformed or incomplete.
    """
    payload = {
        "model": MODEL_NAME,
        "system": _SYSTEM_PROMPT,
        "prompt": (
            "Extract the required information from the following tender document "
            "and return ONLY the JSON object as instructed.\n\n"
            f"TENDER DOCUMENT:\n{parsed_text}"
        ),
        "stream": False,
        "options": {
            "temperature": 0.1,   # Low temperature for deterministic extraction
            "num_predict": 4096,  # Enough tokens for a complete JSON response
        },
    }

    response = requests.post(
        OLLAMA_API_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    response_data: dict = response.json()
    raw_text: str = response_data.get("response", "")

    return parse_strict_json(raw_text)
