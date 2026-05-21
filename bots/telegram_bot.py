# bots/telegram_bot.py
import asyncio
import threading
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from agent.core import Agent
from config import Config


def make_message_handler(agent: Agent):
    async def handle(update: Update, context) -> None:
        if not update.message or not update.message.text:
            return
        session_id = f"telegram:{update.effective_user.id}"
        response = await agent.chat(session_id, update.message.text)
        await update.message.reply_text(response)

    return handle


def register_routes(fastapi_app, agent: Agent, config: Config) -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        return

    bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    bot_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, make_message_handler(agent))
    )

    if config.TELEGRAM_WEBHOOK_URL:
        import secrets
        from starlette.requests import Request
        from starlette.responses import Response, PlainTextResponse

        _secret = secrets.token_hex(32)

        async def telegram_webhook(request: Request) -> Response:
            if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != _secret:
                return PlainTextResponse("Forbidden", status_code=403)
            data = await request.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
            return Response()

        fastapi_app.add_route("/telegram/webhook", telegram_webhook, methods=["POST"])

        async def _set_webhook():
            await bot_app.initialize()
            await bot_app.bot.set_webhook(
                url=f"{config.TELEGRAM_WEBHOOK_URL}/telegram/webhook",
                secret_token=_secret,
            )

        fastapi_app.add_event_handler("startup", _set_webhook)
    else:
        def _run_polling():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(bot_app.run_polling(stop_signals=None))

        thread = threading.Thread(target=_run_polling, daemon=True)
        thread.start()
