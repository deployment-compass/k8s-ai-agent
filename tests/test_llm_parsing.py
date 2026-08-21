import pytest
from pydantic import BaseModel

from app.llm.base import LLMParseError
from app.llm.parsing import extract_json_object, validate_structured_output


class Output(BaseModel):
    answer: str
    score: int


def test_extracts_plain_json():
    data = extract_json_object('{"answer": "hi", "score": 1}')
    assert data == {"answer": "hi", "score": 1}


def test_extracts_json_from_markdown_fences():
    content = "```json\n{\"answer\": \"hi\", \"score\": 2}\n```"
    data = extract_json_object(content)
    assert data == {"answer": "hi", "score": 2}


def test_extracts_json_with_surrounding_prose():
    content = 'Here you go:\n{"answer": "hi", "score": 3}\nHope that helps!'
    data = extract_json_object(content)
    assert data == {"answer": "hi", "score": 3}


def test_raises_when_no_json_present():
    with pytest.raises(LLMParseError):
        extract_json_object("no json here at all")


def test_raises_on_invalid_json():
    with pytest.raises(LLMParseError):
        extract_json_object('{"answer": "hi", score: }')


def test_raises_on_non_object_json():
    with pytest.raises(LLMParseError):
        extract_json_object("[1, 2, 3]")


def test_validate_success():
    parsed = validate_structured_output('{"answer": "ok", "score": 5}', Output)
    assert parsed.answer == "ok"
    assert parsed.score == 5


def test_validate_fails_on_missing_field():
    with pytest.raises(LLMParseError):
        validate_structured_output('{"answer": "ok"}', Output)


def test_validate_coerces_types():
    parsed = validate_structured_output('{"answer": "ok", "score": "7"}', Output)
    assert parsed.score == 7
