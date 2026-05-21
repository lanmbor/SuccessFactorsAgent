# sf/client.py
import httpx
from sf.auth import SFAuth


class SFClient:
    def __init__(self, auth: SFAuth, base_url: str):
        self._auth = auth
        self._base_url = base_url.rstrip("/")

    async def _auth_headers(self) -> dict:
        token = await self._auth.get_token()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def get_metadata(self) -> str:
        headers = await self._auth_headers()
        headers["Accept"] = "application/xml"
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self._base_url}/odata/v2/$metadata", headers=headers)
            r.raise_for_status()
            return r.text

    async def query(self, entity: str, **kwargs) -> dict:
        headers = await self._auth_headers()
        params: dict = {"$format": "json"}
        mapping = {
            "filter": "$filter",
            "select": "$select",
            "top": "$top",
            "skip": "$skip",
            "expand": "$expand",
            "orderby": "$orderby",
        }
        for key, odata_key in mapping.items():
            if kwargs.get(key) is not None:
                params[odata_key] = kwargs[key]
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base_url}/odata/v2/{entity}", headers=headers, params=params
            )
            r.raise_for_status()
            return r.json()

    async def create(self, entity: str, data: dict) -> dict:
        headers = await self._auth_headers()
        headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/odata/v2/{entity}", headers=headers, json=data
            )
            r.raise_for_status()
            return r.json()

    async def update(self, entity: str, key: str, data: dict) -> None:
        headers = await self._auth_headers()
        headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{self._base_url}/odata/v2/{entity}({key})", headers=headers, json=data
            )
            r.raise_for_status()

    async def delete(self, entity: str, key: str) -> None:
        headers = await self._auth_headers()
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self._base_url}/odata/v2/{entity}({key})", headers=headers
            )
            r.raise_for_status()
