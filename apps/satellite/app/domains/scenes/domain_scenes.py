from datetime import date


def is_valid_scene_date_range(start_date: date, end_date: date) -> bool:
    """Verifica que la fecha de inicio no sea posterior a la fecha de fin."""
    return start_date <= end_date
