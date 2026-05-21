import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    SF_BASE_URL: str = ""
    SF_COMPANY_ID: str = ""
    SF_USER_ID: str = ""
    SF_CLIENT_ID: str = ""
    SF_PRIVATE_KEY_PATH: str = ""
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""


def load_config() -> Config:
    return Config(
        SF_BASE_URL=os.environ["SF_BASE_URL"],
        SF_COMPANY_ID=os.environ["SF_COMPANY_ID"],
        SF_USER_ID=os.environ["SF_USER_ID"],
        SF_CLIENT_ID=os.environ["SF_CLIENT_ID"],
        SF_PRIVATE_KEY_PATH=os.environ["SF_PRIVATE_KEY_PATH"],
        LLM_PROVIDER=os.environ["LLM_PROVIDER"],
        LLM_MODEL=os.environ["LLM_MODEL"],
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        LLM_API_BASE=os.getenv("LLM_API_BASE", ""),
        TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        TELEGRAM_WEBHOOK_URL=os.getenv("TELEGRAM_WEBHOOK_URL", ""),
        WHATSAPP_TOKEN=os.getenv("WHATSAPP_TOKEN", ""),
        WHATSAPP_PHONE_ID=os.getenv("WHATSAPP_PHONE_ID", ""),
        WHATSAPP_VERIFY_TOKEN=os.getenv("WHATSAPP_VERIFY_TOKEN", ""),
        TWILIO_ACCOUNT_SID=os.getenv("TWILIO_ACCOUNT_SID", ""),
        TWILIO_AUTH_TOKEN=os.getenv("TWILIO_AUTH_TOKEN", ""),
        TWILIO_WHATSAPP_FROM=os.getenv("TWILIO_WHATSAPP_FROM", ""),
    )
