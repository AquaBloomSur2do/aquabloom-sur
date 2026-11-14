from typing import Any


def insert_model_scope_in_db(
    client, db_payload: dict[str, Any]
) -> dict[str, Any] | None:
    result = (
        client.table("scientific_model_scopes").insert(db_payload).execute()
    )
    return result.data[0] if getattr(result, "data", None) else None
