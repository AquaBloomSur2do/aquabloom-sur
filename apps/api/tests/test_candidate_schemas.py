from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dataset.application.schemas import (
    CandidateValidationPayload,
    CandidateVariableMetadata,
    IncorporateCandidatesInput,
)


def test_ph_requires_adimensional_unit():
    metadata = CandidateVariableMetadata(variable="pH", unit="adimensional")

    assert metadata.variable == "pH"


@pytest.mark.parametrize("unit", ["", "   "])
def test_ph_rejects_blank_unit(unit):
    with pytest.raises(ValidationError):
        CandidateVariableMetadata(variable="pH", unit=unit)


def test_candidate_validation_accepts_naive_acquisition_date_as_utc():
    payload = CandidateValidationPayload(
        candidate_id=uuid4(),
        acquisition_date=datetime(2026, 10, 29, 12),       # noqa: DTZ001
        variables=[{"variable": "pH", "unit": "adimensional"}],
    )

    assert payload.acquisition_date.tzinfo == timezone.utc


def test_incorporate_candidates_requires_at_least_one_id():
    with pytest.raises(ValidationError):
        IncorporateCandidatesInput(candidate_ids=[])
