import json

import pytest

from apps.scientific.app.worker import process_raw_task


def test_process_raw_task_computes_summary():
    raw_payload = json.dumps(
        {
            "task_id": "task-001",
            "task_type": "summarize_measurements",
            "measurements": [1.0, 2.0, 3.0],
        }
    )

    result = process_raw_task(raw_payload)

    assert result.task_id == "task-001"
    assert result.count == 3
    assert result.minimum == 1.0
    assert result.maximum == 3.0
    assert result.mean == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("bad_payload", "expected_exc"),
    [
        ("not-json", ValueError),
        ("[]", TypeError),
        (
            json.dumps({"task_type": "summarize_measurements", "measurements": [1.0]}),
            ValueError,
        ),
        (
            json.dumps(
                {"task_id": "t1", "task_type": "unknown", "measurements": [1.0]}
            ),
            ValueError,
        ),
        (
            json.dumps(
                {
                    "task_id": "t1",
                    "task_type": "summarize_measurements",
                    "measurements": "not-a-list",
                }
            ),
            TypeError,
        ),
        (
            json.dumps(
                {
                    "task_id": "t1",
                    "task_type": "summarize_measurements",
                    "measurements": [],
                }
            ),
            ValueError,
        ),
        (
            json.dumps(
                {
                    "task_id": "t1",
                    "task_type": "summarize_measurements",
                    "measurements": [True],
                }
            ),
            TypeError,
        ),
    ],
)
def test_process_raw_task_rejects_invalid_payloads(
    bad_payload: str,
    expected_exc: type[Exception],
):
    with pytest.raises(expected_exc):
        process_raw_task(bad_payload)

