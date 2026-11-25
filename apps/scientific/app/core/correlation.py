import re
from uuid import uuid4

CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")


def resolve_correlation_id(value: str | None) -> str:
    candidate = value.strip() if value else ""
    if CORRELATION_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())
