import hashlib


def short_sha256(value: str, size: int = 32) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:size]
