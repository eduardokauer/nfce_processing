import re


def parse_brl_money(value: str | None) -> float | None:
    if not value:
        return None
    normalized = re.sub(r"[^\d,.-]", "", value)
    if not normalized:
        return None
    normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None
