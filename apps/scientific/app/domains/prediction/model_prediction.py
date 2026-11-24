from typing import Any


def insert_prediction_in_db(
    client, db_payload: dict[str, Any]
) -> dict[str, Any] | None:
    result = (
        client.schema("scientific").table("predictions").insert(db_payload).execute()
    )
    return result.data[0] if getattr(result, "data", None) else None
