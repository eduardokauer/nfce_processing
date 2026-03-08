from datetime import datetime


def parse_datetime_br(value: str | None) -> tuple[str | None, str | None, str | None, str | None, int | None]:
    if not value:
        return None, None, None, None, None
    value = value.strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            iso = dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), iso, dt.strftime("%Y-%m"), dt.year
        except ValueError:
            continue
    return None, None, None, None, None
