# tests/test_agent.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.core import Agent


@pytest.fixture
def mock_sf_client():
    return AsyncMock()


@pytest.fixture
def agent(mock_sf_client, cfg):
    return Agent(sf_client=mock_sf_client, config=cfg)


def _make_llm_response(content: str, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_chat_returns_string_response(agent):
    with patch("litellm.acompletion", new=AsyncMock(return_value=_make_llm_response("Hello!"))):
        result = await agent.chat("session1", "Hi")
    assert result == "Hello!"


@pytest.mark.asyncio
async def test_chat_maintains_history_per_session(agent):
    responses = [_make_llm_response("Hi"), _make_llm_response("How are you?")]
    with patch("litellm.acompletion", new=AsyncMock(side_effect=responses)):
        await agent.chat("session1", "Hello")
        await agent.chat("session1", "What is 2+2?")
    history = agent._sessions["session1"]
    user_messages = [m for m in history if m.get("role") == "user"]
    assert len(user_messages) == 2


@pytest.mark.asyncio
async def test_chat_sessions_are_isolated(agent):
    with patch("litellm.acompletion", new=AsyncMock(return_value=_make_llm_response("Hi"))):
        await agent.chat("session_a", "Hello from A")
        await agent.chat("session_b", "Hello from B")
    assert "session_a" in agent._sessions
    assert "session_b" in agent._sessions
    assert agent._sessions["session_a"] != agent._sessions["session_b"]


@pytest.mark.asyncio
async def test_chat_calls_tool_and_returns_final_response(agent, mock_sf_client):
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = "sf_list_entities"
    tool_call.function.arguments = "{}"

    first_response = _make_llm_response(None, tool_calls=[tool_call])
    second_response = _make_llm_response("Found entities: PerPerson")

    mock_sf_client.get_metadata.return_value = """<?xml version="1.0"?>
    <edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"
               xmlns:edm="http://schemas.microsoft.com/ado/2008/09/edm">
      <edmx:DataServices><edm:Schema>
        <edm:EntityContainer><edm:EntitySet Name="PerPerson"/></edm:EntityContainer>
      </edm:Schema></edmx:DataServices></edmx:Edmx>"""

    with patch("litellm.acompletion", new=AsyncMock(side_effect=[first_response, second_response])):
        result = await agent.chat("session1", "List entities")

    assert result == "Found entities: PerPerson"
