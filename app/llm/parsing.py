import json

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMParseError


def extract_json_object(content: str) -> dict:
    """Extract a JSON object from model output.

    Tolerates markdown fences and surrounding prose by taking the
    text between the first '{' and the last '}'.
    """
    text = content.strip()

    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMParseError("Model output does not contain a JSON object.")

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"Model output is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMParseError("Model output is not a JSON object.")
    return parsed


def validate_structured_output(content: str, model_class: type[BaseModel]) -> BaseModel:
    """Parse and validate raw model content against a Pydantic schema."""
    data = extract_json_object(content)
    try:
        return model_class.model_validate(data)
    except ValidationError as exc:
        raise LLMParseError(f"Model output failed schema validation: {exc}") from exc
