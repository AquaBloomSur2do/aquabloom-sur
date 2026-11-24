import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SATELLITE_APP_DIR = REPO_ROOT / "apps" / "satellite" / "app"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"


def _extract_service_block(compose_text: str, service_name: str) -> str:
    lines = compose_text.splitlines()
    target_header = f"  {service_name}:"
    start_idx = None

    for idx, line in enumerate(lines):
        if line == target_header:
            start_idx = idx
            break

    assert start_idx is not None, (
        f"Servicio '{service_name}' no declarado en compose.yaml"
    )

    block_lines = [lines[start_idx]]
    for line in lines[start_idx + 1 :]:
        if line and not line.startswith("    ") and not line.startswith("  #"):
            break
        block_lines.append(line)
    return "\n".join(block_lines)


def test_satellite_has_no_cross_service_imports():
    """Garantiza que Satellite no importe módulos internos de Core ni Scientific (S2-186)."""
    forbidden_prefixes = ("apps.api", "apps.scientific")
    violations: list[str] = []

    for py_file in sorted(SATELLITE_APP_DIR.rglob("*.py")):
        tree = ast.parse(
            py_file.read_text(encoding="utf-8"),
            filename=str(py_file),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}: import {alias.name}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith(forbidden_prefixes)
            ):
                violations.append(
                    f"{py_file.relative_to(REPO_ROOT)}: from {node.module} import ..."
                )

    assert violations == [], f"Imports acoplados detectados en Satellite: {violations}"


def test_compose_declares_isolated_build_and_deployment_for_satellite():
    """Verifica que Satellite y Scientific tengan Dockerfiles y contextos aislados en compose.yaml."""
    assert (REPO_ROOT / "apps" / "api" / "Dockerfile").is_file()
    assert (REPO_ROOT / "apps" / "satellite" / "Dockerfile").is_file()
    assert (REPO_ROOT / "apps" / "scientific" / "Dockerfile").is_file()

    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    satellite_block = _extract_service_block(compose_text, "satellite")
    scientific_block = _extract_service_block(compose_text, "scientific")
    core_block = _extract_service_block(compose_text, "core")

    assert "context: ./apps/satellite" in satellite_block
    assert "dockerfile: Dockerfile" in satellite_block
    assert "core:" not in satellite_block
    assert "scientific:" not in satellite_block

    assert "context: ./apps/scientific" in scientific_block
    assert "dockerfile: Dockerfile" in scientific_block
    assert "satellite:" not in scientific_block
    assert "core:" not in scientific_block

    assert "dockerfile: apps/api/Dockerfile" in core_block
    assert "satellite:" not in core_block
    assert "scientific:" not in core_block



