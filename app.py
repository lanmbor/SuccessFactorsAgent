# app.py
import chainlit as cl
from config import load_config
from sf.auth import SFAuth
from sf.client import SFClient
from agent.core import Agent

_config = load_config()
_auth = SFAuth(_config)
_sf_client = SFClient(auth=_auth, base_url=_config.SF_BASE_URL)
_agent = Agent(sf_client=_sf_client, config=_config)


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content="Hello! I'm your SuccessFactors assistant. Ask me anything about your SF data."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.context.session.id
    response = await _agent.chat(session_id, message.content)
    await cl.Message(content=response).send()


# Register bot webhook routes if credentials are configured
if _config.TELEGRAM_BOT_TOKEN or _config.WHATSAPP_TOKEN or _config.TWILIO_ACCOUNT_SID:
    from chainlit.server import app as _fastapi_app
    from bots.telegram_bot import register_routes as _reg_telegram
    from bots.whatsapp_bot import register_routes as _reg_whatsapp
    _reg_telegram(_fastapi_app, _agent, _config)
    _reg_whatsapp(_fastapi_app, _agent, _config)
