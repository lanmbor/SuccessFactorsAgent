# bots/whatsapp_bot.py
import httpx
from config import Config
from agent.core import Agent


def extract_meta_message(payload: dict):
    try:
        messages = payload["entry"][0]["changes"][0]["value"].get("messages", [])
        if not messages:
            return None
        msg = messages[0]
        return msg["from"], msg["text"]["body"]
    except (KeyError, IndexError, TypeError):
        return None


async def send_meta_reply(to: str, text: str, config: Config) -> None:
    url = f"https://graph.facebook.com/v18.0/{config.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()


def register_routes(fastapi_app, agent: Agent, config: Config) -> None:
    if config.WHATSAPP_TOKEN:
        _register_meta_routes(fastapi_app, agent, config)
    elif config.TWILIO_ACCOUNT_SID:
        _register_twilio_routes(fastapi_app, agent, config)


def _register_meta_routes(fastapi_app, agent: Agent, config: Config) -> None:
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse, JSONResponse

    @fastapi_app.get("/whatsapp/webhook")
    async def meta_verify(request: Request):
        params = dict(request.query_params)
        if (
            params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN
        ):
            return PlainTextResponse(params["hub.challenge"])
        return PlainTextResponse("Forbidden", status_code=403)

    @fastapi_app.post("/whatsapp/webhook")
    async def meta_webhook(request: Request):
        payload = await request.json()
        result = extract_meta_message(payload)
        if result:
            sender, text = result
            session_id = f"whatsapp:{sender}"
            response = await agent.chat(session_id, text)
            try:
                await send_meta_reply(sender, response, config)
            except Exception:
                pass  # don't fail the webhook if the reply fails
        return JSONResponse({"status": "ok"})


def _register_twilio_routes(fastapi_app, agent: Agent, config: Config) -> None:
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse
    from twilio.twiml.messaging_response import MessagingResponse
    from twilio.request_validator import RequestValidator

    @fastapi_app.post("/whatsapp/twilio")
    async def twilio_webhook(request: Request):
        form = await request.form()
        form_dict = dict(form)
        url = str(request.url)
        signature = request.headers.get("X-Twilio-Signature", "")
        validator = RequestValidator(config.TWILIO_AUTH_TOKEN)
        if not validator.validate(url, form_dict, signature):
            return PlainTextResponse("Forbidden", status_code=403)
        sender = form_dict.get("From", "")
        text = form_dict.get("Body", "")
        if sender and text:
            session_id = f"whatsapp:{sender}"
            response_text = await agent.chat(session_id, text)
            resp = MessagingResponse()
            resp.message(response_text)
            return PlainTextResponse(str(resp), media_type="application/xml")
        return PlainTextResponse("", media_type="application/xml")
