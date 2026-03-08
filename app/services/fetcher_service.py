import httpx

from app.core.config import settings


class FetchError(Exception):
    pass


async def fetch_nfce_html(url: str) -> str:
    headers = {"User-Agent": settings.user_agent}
    timeout = settings.request_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"Falha ao buscar NFC-e: {exc}") from exc
    return response.text
