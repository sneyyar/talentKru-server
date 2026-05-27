"""
OpenAPI metadata enforcement helpers.

Provides utilities to validate that all FastAPI routes and Pydantic model fields
meet the OpenAPI documentation standards required for AI agent compatibility.

Requirements: 5.1, 5.2, 5.3
"""

import re
from typing import Type

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

SNAKE_CASE_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def validate_route_metadata(app: FastAPI) -> list[str]:
    """
    Iterate all APIRoute objects and check OpenAPI metadata requirements.

    Checks that every route has:
    - operation_id in snake_case format
    - summary of at most 80 characters
    - description of at least 20 characters

    Returns a list of violation strings (empty if all routes are compliant).

    Requirements: 5.1
    """
    violations = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path

        # Check operation_id
        if not route.operation_id:
            violations.append(f"{path}: missing operation_id")
        elif not SNAKE_CASE_RE.match(route.operation_id):
            violations.append(
                f"{path}: operation_id '{route.operation_id}' is not snake_case"
            )

        # Check summary
        if not route.summary:
            violations.append(f"{path}: missing summary")
        elif len(route.summary) > 80:
            violations.append(
                f"{path}: summary exceeds 80 chars ({len(route.summary)})"
            )

        # Check description
        if not route.description:
            violations.append(f"{path}: missing description")
        elif len(route.description) < 20:
            violations.append(
                f"{path}: description too short ({len(route.description)} < 20)"
            )

    return violations


def validate_pydantic_field_descriptions(model_class: Type[BaseModel]) -> list[str]:
    """
    Check that every field in a Pydantic model has a description of at least 10 characters.

    Iterates all FieldInfo entries in the model's model_fields and verifies each
    has a non-empty description string of at least 10 characters.

    Returns a list of violation strings (empty if all fields are compliant).

    Requirements: 5.2
    """
    violations = []
    for field_name, field_info in model_class.model_fields.items():
        desc = field_info.description
        if not desc:
            violations.append(
                f"{model_class.__name__}.{field_name}: missing description"
            )
        elif len(desc) < 10:
            violations.append(
                f"{model_class.__name__}.{field_name}: description too short "
                f"({len(desc)} < 10)"
            )
    return violations


def assert_route_metadata(app: FastAPI) -> None:
    """
    Raise AssertionError if any route violates OpenAPI metadata requirements.

    Intended for use in startup checks or test suites to enforce that all
    registered routes carry the required operation_id, summary, and description.

    Requirements: 5.1
    """
    violations = validate_route_metadata(app)
    if violations:
        raise AssertionError(
            "OpenAPI metadata violations found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


def assert_pydantic_field_descriptions(model_class: Type[BaseModel]) -> None:
    """
    Raise AssertionError if any field violates description requirements.

    Intended for use in startup checks or test suites to enforce that all
    Pydantic model fields used in request/response schemas carry adequate
    Field(description=...) annotations.

    Requirements: 5.2
    """
    violations = validate_pydantic_field_descriptions(model_class)
    if violations:
        raise AssertionError(
            "Pydantic field description violations found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
