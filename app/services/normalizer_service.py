import re


def digits_only(value: str | None) -> str | None:
    if not value:
        return None
    result = re.sub(r"\D", "", value)
    return result or None


def normalize_description(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()
