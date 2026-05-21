# tests/test_whatsapp.py
import pytest
import respx
import httpx
import json
from unittest.mock import AsyncMock
from bots.whatsapp_bot import extract_meta_message, send_meta_reply


def test_extract_meta_message_returns_sender_and_text():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "1234567890", "text": {"body": "Hello SF"}}]
                }
            }]
        }]
    }
    sender, text = extract_meta_message(payload)
    assert sender == "1234567890"
    assert text == "Hello SF"


def test_extract_meta_message_returns_none_for_non_message():
    payload = {"entry": [{"changes": [{"value": {}}]}]}
    result = extract_meta_message(payload)
    assert result is None


@pytest.mark.asyncio
async def test_send_meta_reply_posts_to_graph_api(cfg):
    cfg.WHATSAPP_TOKEN = "test-wa-token"
    cfg.WHATSAPP_PHONE_ID = "phone-123"
    with respx.mock:
        route = respx.post(
            "https://graph.facebook.com/v18.0/phone-123/messages"
        ).mock(return_value=httpx.Response(200, json={"messages": [{"id": "mid"}]}))
        await send_meta_reply("1234567890", "Hello back", cfg)
    assert route.call_count == 1
    sent = route.calls[0].request
    body = json.loads(sent.content)
    assert body["to"] == "1234567890"
    assert body["text"]["body"] == "Hello back"
