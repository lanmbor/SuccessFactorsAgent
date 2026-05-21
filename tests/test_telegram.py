# tests/test_telegram.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from bots.telegram_bot import make_message_handler


@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.chat.return_value = "Here is your SF data."
    return agent


@pytest.mark.asyncio
async def test_handler_calls_agent_with_telegram_session_id(mock_agent):
    handler = make_message_handler(mock_agent)
    update = MagicMock()
    update.effective_user.id = 12345
    update.message.text = "Show me employee list"
    update.message.reply_text = AsyncMock()
    await handler(update, MagicMock())
    mock_agent.chat.assert_called_once_with("telegram:12345", "Show me employee list")


@pytest.mark.asyncio
async def test_handler_sends_agent_reply(mock_agent):
    handler = make_message_handler(mock_agent)
    update = MagicMock()
    update.effective_user.id = 99
    update.message.text = "Hello"
    update.message.reply_text = AsyncMock()
    await handler(update, MagicMock())
    update.message.reply_text.assert_called_once_with("Here is your SF data.")


@pytest.mark.asyncio
async def test_handler_ignores_empty_message(mock_agent):
    handler = make_message_handler(mock_agent)
    update = MagicMock()
    update.message = None
    await handler(update, MagicMock())
    mock_agent.chat.assert_not_called()
