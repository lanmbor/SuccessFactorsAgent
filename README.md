# SF Agent

An AI-powered chatbot that lets you query and update SAP SuccessFactors data through natural language. Accessible via a browser chat UI, Telegram, and WhatsApp.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Frontends                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Chainlit UI │  │ Telegram Bot │  │  WhatsApp  │  │
│  │  (browser)   │  │  (adapter)   │  │  (adapter) │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
└─────────┼─────────────────┼────────────────┼──────────┘
          └─────────────────┼────────────────┘
                            ▼
              ┌─────────────────────────┐
              │  Agent Core             │
              │  ReAct loop · Memory    │
              └────────────┬────────────┘
                 ┌─────────┴─────────┐
                 ▼                   ▼
          ┌───────────┐    ┌──────────────────┐
          │  LiteLLM  │    │  SF OData Client │
          │ (any LLM) │    │  OAuth2 SAML2    │
          └───────────┘    └────────┬─────────┘
                                    ▼
                       ┌────────────────────────┐
                       │  SAP SuccessFactors API │
                       └────────────────────────┘
```

## Prerequisites

- Python 3.11+
- SAP SuccessFactors tenant with an OAuth2 client application configured
- An LLM API key (OpenAI, Anthropic, Azure, or a local model via Ollama)

## Setup

**1. Clone and install dependencies:**
```bash
git clone <repo-url>
cd sf-agent
pip install -r requirements.txt
```

**2. Configure credentials:**
```bash
cp .env.example .env
```
Edit `.env` with your credentials (see [Configuration](#configuration) below).

**3. Generate and register an X.509 certificate in SF Admin Center:**
```bash
openssl req -x509 -newkey rsa:2048 -keyout certs/private_key.pem -out certs/certificate.pem \
  -days 365 -nodes -subj "/CN=sf-agent" \
  -addext "keyUsage=critical,digitalSignature,nonRepudiation"
```
Upload `certs/certificate.pem` to:
**SF Admin Center → OAuth2 Client Applications → your client → Certificate field**

## Running Locally

```bash
python -m chainlit run app.py
```

Open `http://localhost:8000` in your browser.

## Configuration

Copy `.env.example` to `.env` and fill in the values:

### SuccessFactors

| Variable | Description |
|---|---|
| `SF_BASE_URL` | SF API host, e.g. `https://api4.successfactors.com` |
| `SF_COMPANY_ID` | Your SF company/tenant ID |
| `SF_USER_ID` | Admin user ID used to authenticate |
| `SF_CLIENT_ID` | API key from SF Admin Center → OAuth2 Client Applications |
| `SF_PRIVATE_KEY_PATH` | Path to the private key PEM file |
| `SF_CERTIFICATE_PATH` | Path to the certificate PEM file |

### LLM Provider

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | Provider: `openai`, `anthropic`, `azure`, `ollama`, … |
| `LLM_MODEL` | Model name, e.g. `gpt-4o`, `claude-opus-4-7`, `llama3.2` |
| `LLM_API_KEY` | API key (leave blank for local Ollama) |
| `LLM_API_BASE` | Optional: custom endpoint for Azure or local proxies |

**Examples:**
```env
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-opus-4-7
LLM_API_KEY=sk-ant-...

# Local Ollama (no key needed)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_BASE=http://localhost:11434
```

## Docker Deployment

**1. Place your certificates in `./certs/`** and set paths in `.env`:
```env
SF_PRIVATE_KEY_PATH=/app/certs/private_key.pem
SF_CERTIFICATE_PATH=/app/certs/certificate.pem
```

**2. Build and start:**
```bash
docker compose up --build
```

Run in background:
```bash
docker compose up --build -d
```

Stop:
```bash
docker compose down
```

## Bot Integrations

Bots are optional. Leave the credentials blank in `.env` to disable them.

### Telegram

Add to `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-public-url.com   # optional: omit to use polling mode
```

- **Without `TELEGRAM_WEBHOOK_URL`** — runs in polling mode (works locally, no public URL needed)
- **With `TELEGRAM_WEBHOOK_URL`** — registers a webhook on startup (requires public HTTPS URL)

### WhatsApp — Meta Cloud API

Requires a WhatsApp Business account and a public HTTPS URL for webhook verification.

```env
WHATSAPP_TOKEN=your_permanent_token
WHATSAPP_PHONE_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=any_secret_string
```

Set webhook URL in Meta Developer Console: `https://your-domain.com/whatsapp/webhook`

### WhatsApp — Twilio Sandbox

Easier for testing — no WhatsApp Business account needed. Requires a public URL (e.g. via ngrok).

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

Set sandbox webhook in Twilio Console: `https://your-ngrok-url/whatsapp/twilio`

## Available Tools

The agent uses 6 general-purpose OData tools that work with any SF entity:

| Tool | Description |
|---|---|
| `sf_list_entities` | List all available entity sets in your SF tenant |
| `sf_get_schema` | Get field names, types, and key properties for an entity |
| `sf_query` | Query records with `$filter`, `$select`, `$top`, `$skip`, `$expand`, `$orderby` |
| `sf_create` | Create a new record |
| `sf_update` | Update fields on an existing record |
| `sf_delete` | Delete a record (always confirms with user first) |

## Project Structure

```
sf-agent/
├── app.py                  # Chainlit entry point
├── agent/
│   ├── core.py             # ReAct loop, LiteLLM calls, tool dispatch
│   └── tools.py            # 6 OData tool definitions
├── sf/
│   ├── auth.py             # OAuth2 SAML2 Bearer token handling
│   └── client.py           # OData HTTP client
├── bots/
│   ├── telegram_bot.py     # Telegram adapter
│   └── whatsapp_bot.py     # WhatsApp adapter (Meta Cloud API or Twilio)
├── config.py               # Config loading from .env
├── .env.example            # Credential template
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```
