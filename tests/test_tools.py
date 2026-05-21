# tests/test_tools.py
import pytest
import json
from unittest.mock import AsyncMock
from agent.tools import sf_list_entities, sf_get_schema, sf_query, sf_create, sf_update, sf_delete, TOOLS

SAMPLE_METADATA = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"
           xmlns:edm="http://schemas.microsoft.com/ado/2008/09/edm">
  <edmx:DataServices>
    <edm:Schema>
      <edm:EntityType Name="PerPerson">
        <edm:Key><edm:PropertyRef Name="personIdExternal"/></edm:Key>
        <edm:Property Name="personIdExternal" Type="Edm.String" Nullable="false"/>
        <edm:Property Name="firstName" Type="Edm.String" Nullable="true"/>
        <edm:Property Name="lastName" Type="Edm.String" Nullable="true"/>
      </edm:EntityType>
      <edm:EntityType Name="EmpJob">
        <edm:Key><edm:PropertyRef Name="userId"/></edm:Key>
        <edm:Property Name="userId" Type="Edm.String" Nullable="false"/>
        <edm:Property Name="department" Type="Edm.String" Nullable="true"/>
      </edm:EntityType>
      <edm:EntityContainer>
        <edm:EntitySet Name="PerPerson" EntityType="edm:PerPerson"/>
        <edm:EntitySet Name="EmpJob" EntityType="edm:EmpJob"/>
      </edm:EntityContainer>
    </edm:Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_metadata.return_value = SAMPLE_METADATA
    return client


@pytest.mark.asyncio
async def test_sf_list_entities_returns_sorted_names(mock_client):
    result = await sf_list_entities(mock_client)
    assert result == "EmpJob\nPerPerson"


@pytest.mark.asyncio
async def test_sf_get_schema_shows_key_fields(mock_client):
    result = await sf_get_schema(mock_client, "PerPerson")
    assert "[KEY]" in result
    assert "personIdExternal" in result


@pytest.mark.asyncio
async def test_sf_get_schema_shows_all_properties(mock_client):
    result = await sf_get_schema(mock_client, "PerPerson")
    assert "firstName" in result
    assert "lastName" in result


@pytest.mark.asyncio
async def test_sf_get_schema_unknown_entity(mock_client):
    result = await sf_get_schema(mock_client, "NonExistent")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_sf_query_returns_json_string(mock_client):
    mock_client.query.return_value = {"d": {"results": [{"userId": "U001"}]}}
    result = await sf_query(mock_client, "PerPerson", filter="userId eq 'U001'")
    parsed = json.loads(result)
    assert parsed["d"]["results"][0]["userId"] == "U001"


@pytest.mark.asyncio
async def test_sf_create_returns_json_string(mock_client):
    mock_client.create.return_value = {"d": {"userId": "U002"}}
    result = await sf_create(mock_client, "PerPerson", {"userId": "U002"})
    parsed = json.loads(result)
    assert parsed["d"]["userId"] == "U002"


@pytest.mark.asyncio
async def test_sf_update_returns_success_message(mock_client):
    mock_client.update.return_value = None
    result = await sf_update(mock_client, "PerPerson", "userId='U001'", {"firstName": "John"})
    assert "success" in result.lower()


@pytest.mark.asyncio
async def test_sf_delete_returns_success_message(mock_client):
    mock_client.delete.return_value = None
    result = await sf_delete(mock_client, "PerPerson", "userId='U001'")
    assert "success" in result.lower()


def test_tools_list_has_six_entries():
    assert len(TOOLS) == 6


def test_tools_list_has_correct_names():
    names = {t["function"]["name"] for t in TOOLS}
    assert names == {
        "sf_list_entities", "sf_get_schema", "sf_query",
        "sf_create", "sf_update", "sf_delete"
    }


def test_tools_list_entries_are_valid_function_type():
    for tool in TOOLS:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
