"""Event schema helpers shared by K80 services."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft7Validator, ValidationError

SCHEMA_FILE = Path(__file__).parent / "event_schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    with SCHEMA_FILE.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    return Draft7Validator(schema)


def validate_event(event: Dict[str, Any]) -> None:
    """Raise `ValidationError` if the event does not conform to the schema."""
    validator = _validator()
    errors = list(validator.iter_errors(event))
    if errors:
        # Raise the first error for simplicity
        raise ValidationError(errors[0].message)


def build_event(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Return the event if it passes schema validation, else raise `ValidationError`."""
    validate_event(candidate)
    return candidate
