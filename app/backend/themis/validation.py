from __future__ import annotations

import re
from copy import deepcopy
from string import Formatter
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError


FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def validate_schema_document(schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(exc.message) from exc


def validate_payload(schema: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
    validator = Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        errors.append(
            {
                "path": ".".join(str(part) for part in err.path),
                "message": err.message,
                "validator": err.validator,
            }
        )
    return errors


def validate_required_and_types(schema: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
    loose_schema = _strip_additional_properties(schema)
    return validate_payload(loose_schema, payload)


def _strip_additional_properties(value: Any) -> Any:
    if isinstance(value, dict):
        next_value = {}
        for key, child in value.items():
            if key == "additionalProperties":
                continue
            next_value[key] = _strip_additional_properties(child)
        return next_value
    if isinstance(value, list):
        return [_strip_additional_properties(item) for item in value]
    return deepcopy(value)


def validate_merge_template(template: str | None) -> None:
    if not template:
        return
    for _, field_name, format_spec, conversion in Formatter().parse(template):
        if format_spec or conversion:
            raise ValueError("Merge template only supports simple {field} placeholders")
        if field_name and not FIELD_RE.match(field_name):
            raise ValueError(f"Invalid placeholder: {field_name}")


def _lookup(payload: dict[str, Any], field_name: str) -> Any:
    value: Any = payload
    for part in field_name.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(field_name)
        value = value[part]
    return value


def render_merge_template(template: str | None, payload: dict[str, Any]) -> str:
    if not template:
        return str(payload)
    validate_merge_template(template)
    rendered = []
    for literal, field_name, _, _ in Formatter().parse(template):
        rendered.append(literal)
        if field_name:
            value = _lookup(payload, field_name)
            rendered.append("" if value is None else str(value))
    return "".join(rendered)


def validation_exception_to_message(exc: ValidationError) -> str:
    return exc.message
