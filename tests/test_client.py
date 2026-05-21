# tests/test_client.py
import pytest
import respx
import httpx
from unittest.mock import AsyncMock
from sf.client import SFClient


@pytest.fixture
def mock_auth():
    auth = AsyncMock()
    auth.get_token.return_value = "test-bearer-token"
    return auth


@pytest.fixture
def client(mock_auth, cfg):
    return SFClient(auth=mock_auth, base_url=cfg.SF_BASE_URL)


@pytest.mark.asyncio
async def test_query_sends_get_with_odata_params(client):
    with respx.mock:
        route = respx.get("https://test.successfactors.com/odata/v2/PerPerson").mock(
            return_value=httpx.Response(200, json={"d": {"results": []}})
        )
        result = await client.query("PerPerson", filter="userId eq 'U001'", top=10)
    assert result == {"d": {"results": []}}
    url_str = str(route.calls[0].request.url)
    assert "$filter" in url_str or "%24filter" in url_str


@pytest.mark.asyncio
async def test_query_includes_bearer_token(client, mock_auth):
    with respx.mock:
        route = respx.get("https://test.successfactors.com/odata/v2/PerPerson").mock(
            return_value=httpx.Response(200, json={"d": {"results": []}})
        )
        await client.query("PerPerson")
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-bearer-token"


@pytest.mark.asyncio
async def test_create_sends_post(client):
    with respx.mock:
        route = respx.post("https://test.successfactors.com/odata/v2/PerPerson").mock(
            return_value=httpx.Response(201, json={"d": {"userId": "U002"}})
        )
        result = await client.create("PerPerson", {"userId": "U002", "firstName": "Jane"})
    assert result == {"d": {"userId": "U002"}}
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_update_sends_patch(client):
    with respx.mock:
        route = respx.patch(
            "https://test.successfactors.com/odata/v2/PerPerson(userId='U001')"
        ).mock(return_value=httpx.Response(204))
        await client.update("PerPerson", "userId='U001'", {"firstName": "John"})
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_delete_sends_delete(client):
    with respx.mock:
        route = respx.delete(
            "https://test.successfactors.com/odata/v2/PerPerson(userId='U001')"
        ).mock(return_value=httpx.Response(204))
        await client.delete("PerPerson", "userId='U001'")
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_get_metadata_returns_xml_string(client):
    xml = b"<?xml version='1.0'?><root/>"
    with respx.mock:
        respx.get("https://test.successfactors.com/odata/v2/$metadata").mock(
            return_value=httpx.Response(200, content=xml, headers={"Content-Type": "application/xml"})
        )
        result = await client.get_metadata()
    assert isinstance(result, str)
    assert "<root" in result
