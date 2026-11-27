import hashlib
import json
from pathlib import Path

import pytest

from apps.api.app.domains.library.service_library import (
    retrieve_and_verify_library_file,
    store_library_file_with_checksum,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "scientific"
    / "tests"
    / "fixtures"
    / "library"
)
CSV_PATH = FIXTURE_DIR / "sample_library.csv"
MANIFEST_PATH = FIXTURE_DIR / "sample_library.manifest.json"

RESOURCE_ID = "11111111-1111-4111-8111-111111111111"
VERSION_ID = "22222222-2222-4222-8222-222222222222"


class FakeStorageBucket:
    def __init__(self, store: dict[str, bytes]):
        self._store = store
        self.last_file_options: dict[str, str] | None = None

    def upload(
        self,
        path: str,
        content: bytes,
        file_options: dict[str, str] | None = None,
    ) -> dict[str, str]:
        self._store[path] = bytes(content)
        self.last_file_options = file_options
        return {"path": path}

    def download(self, path: str) -> bytes:
        if path not in self._store:
            raise FileNotFoundError(f"Archivo no encontrado en Storage: {path}")
        return self._store[path]


class FakeStorageClient:
    def __init__(self):
        self.buckets: dict[str, FakeStorageBucket] = {}
        self.raw_objects: dict[str, dict[str, bytes]] = {}

    def from_(self, bucket_name: str) -> FakeStorageBucket:
        if bucket_name not in self.buckets:
            backing: dict[str, bytes] = {}
            self.raw_objects[bucket_name] = backing
            self.buckets[bucket_name] = FakeStorageBucket(backing)
        return self.buckets[bucket_name]


class FakeSupabaseClient:
    def __init__(self):
        self.storage = FakeStorageClient()


def test_stores_sample_library_fixture_with_checksum_and_recovers_identical_bytes():
    original_bytes = CSV_PATH.read_bytes().replace(b"\r\n", b"\n")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    client = FakeSupabaseClient()

    reference = store_library_file_with_checksum(
        client,
        resource_id=RESOURCE_ID,
        version_id=VERSION_ID,
        filename=manifest["file_name"],
        content=original_bytes,
        content_type=manifest["media_type"],
        expected_checksum=manifest["sha256"],
    )

    assert reference["checksum"] == manifest["sha256"]
    assert reference["size_bytes"] == len(original_bytes)
    assert reference["storage_path"] == (
        f"{RESOURCE_ID}/{VERSION_ID}/sample_library.csv"
    )

    recovered_bytes = retrieve_and_verify_library_file(
        client,
        storage_path=reference["storage_path"],
        expected_checksum=reference["checksum"],
        bucket=reference["bucket"],
    )

    assert recovered_bytes == original_bytes
    assert hashlib.sha256(recovered_bytes).hexdigest() == reference["checksum"]


def test_rejects_storage_when_expected_checksum_does_not_match():
    original_bytes = CSV_PATH.read_bytes().replace(b"\r\n", b"\n")
    client = FakeSupabaseClient()
    wrong_checksum = "0" * 64

    with pytest.raises(ValueError, match="no coincide"):
        store_library_file_with_checksum(
            client,
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            filename="sample_library.csv",
            content=original_bytes,
            expected_checksum=wrong_checksum,
        )

    assert client.storage.raw_objects == {}


def test_rejects_corrupted_bytes_on_recovery():
    original_bytes = CSV_PATH.read_bytes().replace(b"\r\n", b"\n")
    client = FakeSupabaseClient()

    reference = store_library_file_with_checksum(
        client,
        resource_id=RESOURCE_ID,
        version_id=VERSION_ID,
        filename="sample_library.csv",
        content=original_bytes,
    )

    client.storage.raw_objects[reference["bucket"]][reference["storage_path"]] = (
        b"corrupted,data\n"
    )

    with pytest.raises(ValueError, match="no coinciden con el checksum"):
        retrieve_and_verify_library_file(
            client,
            storage_path=reference["storage_path"],
            expected_checksum=reference["checksum"],
            bucket=reference["bucket"],
        )


def test_rejects_invalid_filename_path_traversal():
    original_bytes = CSV_PATH.read_bytes().replace(b"\r\n", b"\n")
    client = FakeSupabaseClient()

    with pytest.raises(ValueError, match="segmentos de ruta"):
        store_library_file_with_checksum(
            client,
            resource_id=RESOURCE_ID,
            version_id=VERSION_ID,
            filename="../sample_library.csv",
            content=original_bytes,
        )
