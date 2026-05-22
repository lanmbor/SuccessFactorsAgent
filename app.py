# app.py
import chainlit as cl  # triggers nest_asyncio.apply()

# nest_asyncio is incompatible with anyio on Python 3.14:
#   1. _PyTask doesn't update C-level tracking → asyncio.current_task() returns None
#   2. run_until_complete exits before draining call_soon queue → done callbacks never fire
# Replace anyio.to_thread.run_sync with asyncio.run_in_executor to bypass both issues.
import sys
if sys.version_info >= (3, 14):
    import asyncio
    import asyncio.tasks
    import anyio.to_thread as _anyio_thread

    # Fix: asyncio.current_task() returns None under nest_asyncio on Python 3.14
    # because _PyTask updates the Python-level _current_tasks dict but NOT the
    # C-level tracking that the builtin current_task() reads from.
    # asyncio.timeouts (wait_for) and sniffio both call current_task() — patch both
    # module references to fall back to the Python-level dict.
    _c_current_task = asyncio.tasks.current_task
    def _compat_current_task(loop=None):
        task = _c_current_task(loop)
        if task is not None:
            return task
        try:
            if loop is None:
                loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
        return asyncio.tasks._current_tasks.get(loop)
    asyncio.current_task = _compat_current_task
    asyncio.tasks.current_task = _compat_current_task

    async def _run_sync_compat(func, *args, abandon_on_cancel=False, limiter=None):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    _anyio_thread.run_sync = _run_sync_compat

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
