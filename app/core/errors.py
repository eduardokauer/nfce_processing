from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiError(Exception):
    status_code: int
    message: str
    error_code: str
    details: list[Any] = field(default_factory=list)
