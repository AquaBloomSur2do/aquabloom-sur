import csv
import hashlib
import io
import json
import re
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "library"
CSV_PATH = FIXTURE_DIR / "sample_library.csv"
MANIFEST_PATH = FIXTURE_DIR / "sample_library.manifest.json"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def test_library_fixture_exists_and_matches_manifest_integrity():
    assert CSV_PATH.is_file(), "Falta el archivo fixture sample_library.csv."
    assert MANIFEST_PATH.is_file(), "Falta el manifiesto sample_library.manifest.json."

    csv_bytes = CSV_PATH.read_bytes()
    assert len(csv_bytes) > 0

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["file_name"] == CSV_PATH.name
    assert manifest["media_type"] == "text/csv"
    assert isinstance(manifest["size_bytes"], int)
    assert manifest["size_bytes"] == len(csv_bytes)
    assert manifest["sha256"] == hashlib.sha256(csv_bytes).hexdigest()


def test_library_manifest_declares_permission_provenance_and_attribution_contract():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["origin"] == "synthetic"
    permission = manifest["usage_permission"]
    assert permission["allowed"] is True
    assert permission["license_spdx"] == "CC-BY-4.0"

    attribution = manifest["attribution"]
    assert set(attribution.keys()) == {"author", "license", "version", "source"}

    author = attribution["author"]
    assert author["status"] in {"known", "unknown"}
    if author["status"] == "known":
        assert isinstance(author["name"], str) and author["name"].strip()
    else:
        assert author["name"] is None

    license_info = attribution["license"]
    assert license_info is None or (
        isinstance(license_info.get("spdx_id"), str)
        and bool(license_info["spdx_id"].strip())
    )

    assert SEMVER_PATTERN.match(attribution["version"])

    source = attribution["source"]
    assert isinstance(source["name"], str) and source["name"].strip()
    assert "url" in source


def test_library_fixture_csv_has_deterministic_rows():
    rows = list(csv.DictReader(io.StringIO(CSV_PATH.read_text(encoding="utf-8"))))

    assert len(rows) == 3
    assert [row["sample_id"] for row in rows] == [
        "LIB-SYN-001",
        "LIB-SYN-002",
        "LIB-SYN-003",
    ]
