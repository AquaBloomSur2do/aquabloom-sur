import pytest
from fastapi import HTTPException

from app.datasets import validate_state_transition
from app.schemas import VersionState


def test_valid_version_state_transitions():
    # Transiciones de avance del ciclo de vida
    validate_state_transition(VersionState.DRAFT, VersionState.IN_REVIEW)
    validate_state_transition(VersionState.IN_REVIEW, VersionState.APPROVED)
    validate_state_transition(VersionState.APPROVED, VersionState.PUBLISHED)

    # Transiciones de retorno a borrador
    validate_state_transition(VersionState.IN_REVIEW, VersionState.DRAFT)
    validate_state_transition(VersionState.APPROVED, VersionState.DRAFT)

    # Transiciones hacia archivado
    validate_state_transition(VersionState.DRAFT, VersionState.ARCHIVED)
    validate_state_transition(VersionState.IN_REVIEW, VersionState.ARCHIVED)
    validate_state_transition(VersionState.APPROVED, VersionState.ARCHIVED)
    validate_state_transition(VersionState.PUBLISHED, VersionState.ARCHIVED)


def test_invalid_version_state_transitions_raise_400():
    # Salto directo no permitido (DRAFT a PUBLISHED)
    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.DRAFT, VersionState.PUBLISHED)
    assert exc_info.value.status_code == 400

    # Despublicación no permitida (PUBLISHED a DRAFT)
    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.PUBLISHED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400

    # Intento de modificar una versión archivada
    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.ARCHIVED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400
    