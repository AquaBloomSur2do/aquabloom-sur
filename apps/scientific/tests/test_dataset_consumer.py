import hashlib
import os
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-secret-key")

from app.dataset_consumer import (
    DatasetContractError,
    fetch_and_verify_training_dataset,
)


def test_fetch_and_verify_training_dataset_success():
    version_id = uuid4()
    manifest_id = uuid4()
    csv_bytes = b"temperatura,clorofila_a,turbidez,ph\r\n15.5,2.1,0.5,7.2\r\n"
    checksum = hashlib.sha256(csv_bytes).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer valid-jwt"
        if request.url.path == f"/api/v1/datasets/versions/{version_id}/training-file":
            return httpx.Response(
                200,
                json={
                    "version_id": str(version_id),
                    "manifest_id": str(manifest_id),
                    "variables": ["temperatura", "clorofila_a", "turbidez", "ph"],
                    "checksum": checksum,
                    "download_url": f"/api/v1/datasets/versions/{version_id}/training-file/download",
                },
            )
        if request.url.path == f"/api/v1/datasets/versions/{version_id}/training-file/download":
            return httpx.Response(200, content=csv_bytes)
        return httpx.Response(404)

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://core-api.local",
    )

    result = fetch_and_verify_training_dataset(
        version_id=version_id,
        bearer_token="valid-jwt",
        client=mock_client,
    )

    assert result.manifest.version_id == version_id
    assert result.manifest.checksum == checksum
    assert len(result.rows) == 1
    assert result.rows[0] == {
        "temperatura": 15.5,
        "clorofila_a": 2.1,
        "turbidez": 0.5,
        "ph": 7.2,
    }


def test_fetch_dataset_rejects_checksum_mismatch():
    version_id = uuid4()
    corrupted_bytes = b"temperatura,clorofila_a,turbidez,ph\r\n99.9,9.9,9.9,9.9\r\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/training-file"):
            return httpx.Response(
                200,
                json={
                    "version_id": str(version_id),
                    "manifest_id": str(uuid4()),
                    "variables": ["temperatura", "clorofila_a", "turbidez", "ph"],
                    "checksum": "a" * 64,
                    "download_url": f"/api/v1/datasets/versions/{version_id}/training-file/download",
                },
            )
        return httpx.Response(200, content=corrupted_bytes)

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://core-api.local",
    )

    with pytest.raises(DatasetContractError) as exc_info:
        fetch_and_verify_training_dataset(
            version_id=version_id,
            bearer_token="valid-jwt",
            client=mock_client,
        )

    assert exc_info.value.status_code == 502
    assert "checksum" in exc_info.value.message.lower()


def test_fetch_dataset_rejects_unpublished_or_forbidden_version():
    version_id = uuid4()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "La versión no está publicada."})

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://core-api.local",
    )

    with pytest.raises(DatasetContractError) as exc_info:
        fetch_and_verify_training_dataset(
            version_id=version_id,
            bearer_token="valid-jwt",
            client=mock_client,
        )

    assert exc_info.value.status_code == 403


def test_fetch_dataset_rejects_mismatched_csv_columns():
    version_id = uuid4()
    wrong_columns_csv = b"temperatura,oxigeno\r\n15.5,8.1\r\n"
    checksum = hashlib.sha256(wrong_columns_csv).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/training-file"):
            return httpx.Response(
                200,
                json={
                    "version_id": str(version_id),
                    "manifest_id": str(uuid4()),
                    "variables": ["temperatura", "clorofila_a", "turbidez", "ph"],
                    "checksum": checksum,
                    "download_url": f"/api/v1/datasets/versions/{version_id}/training-file/download",
                },
            )
        return httpx.Response(200, content=wrong_columns_csv)

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://core-api.local",
    )

    with pytest.raises(DatasetContractError) as exc_info:
        fetch_and_verify_training_dataset(
            version_id=version_id,
            bearer_token="valid-jwt",
            client=mock_client,
        )

    assert exc_info.value.status_code == 422
