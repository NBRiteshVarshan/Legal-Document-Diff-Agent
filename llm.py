import ollama
import json
from schemas import ClauseDiff

def compare_clause(clause_id: str, a: str, b: str) -> dict:
    """Queries local Ollama instance with fallback JSON parsing logic."""
    prompt = f"""You are an expert contract compliance auditor. Compare Version A and Version B of [{clause_id}] for semantic variations.

CRITICAL INSTRUCTION: Pay strict, aggressive attention to numeric shifts, currency updates, liability limits, and day/deadline numbers. If a dollar figure, count, or timeline changes, it is mathematically a critical modification. You must classify it as "Obligation Shifted" or "Wording Modified". Do NOT call it "No Material Change".

VERSION A:
{a}

VERSION B:
{b}
"""

    response = ollama.chat(
        model="qwen2.5:7b",  # Swap with phi4-mini if running on limited RAM
        messages=[
            {"role": "system", "content": "You analyze text variations. You must return data conforming strictly to the requested JSON schema layout configuration."},
            {"role": "user", "content": prompt}
        ],
        format=ClauseDiff.model_json_schema(),
        options={"temperature": 0.0}
    )

    result_content = response["message"]["content"]
    
    try:
        return json.loads(result_content)
    except (json.JSONDecodeError, TypeError):
        try:
            validated = ClauseDiff.model_validate_json(result_content)
            return validated.model_dump()
        except Exception:
            return {
                "change_type": "Wording Modified",
                "summary": "Mismatched textual elements found. JSON parsing error hit local model limits.",
                "risk": "None"
            }