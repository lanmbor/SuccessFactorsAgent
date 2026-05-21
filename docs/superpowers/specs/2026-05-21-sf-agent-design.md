# SF Agent — Design Spec

**Date:** 2026-05-21  
**Status:** Approved  

---

## Overview

An AI agent that lets a super-admin user query and update any data in SAP SuccessFactors through natural language. The agent is accessible via a browser chat UI, Telegram, and WhatsApp. It is LLM-agnostic — the provider is configured once at setup time. The system is deployable locally or in the cloud via Docker.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│  Frontends                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Chainlit UI │  │  Telegram Bot│  │ WhatsApp  │  │
│  │  (browser)   │  │  (adapter)   │  │ (adapter) │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
└─────────┼─────────────────┼────────────────┼─────────┘
          └─────────────────┼────────────────┘
                            ▼
┌─────────────────────────────────────────────────────┐
│  Agent Core  (agent/core.py)                         │
│  ReAct loop · Conversation memory · System prompt    │
└────────────────────┬────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌─────────────────┐   ┌──────────────────────────────┐
│  LiteLLM        │   │  SF OData Client             │
│  LLM provider   │   │  auth.py + client.py         │
│  abstraction    │   │  OAuth2 SAML2 Bearer         │
└─────────────────┘   └──────────────┬───────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │  SAP SuccessFactors OData API │
                       └──────────────────────────────┘
```

### Project Layout

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
│   ├── telegram_bot.py     # Telegram adapter (polling or webhook)
│   └── whatsapp_bot.py     # WhatsApp adapter (Meta Cloud API or Twilio)
├── config.py               # Config loading from .env
├── .env.example            # Credential template
├── requirements.txt
└── docker-compose.yml
```

---

## SuccessFactors Authentication

SF uses OAuth2 with XML-signed SAML2 bearer assertions. The agent handles this transparently.

### Flow

1. Build a SAML2 assertion XML document with `issuer`, `subject`, `audience`, and validity timestamps.
2. Sign the assertion using an **enveloped XML signature** with:
   - Digest algorithm: **SHA-256** (`http://www.w3.org/2001/XMLdsig#sha256`)
   - Signature algorithm: **RSA-SHA256** (`http://www.w3.org/2001/XMLdsig#rsa-sha256`)
   - Canonicalization: **Exclusive C14N** (`http://www.w3.org/2001/10/xml-exc-c14n#`)
3. POST the signed assertion to the SF token endpoint as `grant_type=urn:ietf:params:oauth:grant-type:saml2-bearer`.
4. Receive an OAuth2 access token (default TTL: 12 hours).
5. Attach `Authorization: Bearer <token>` to every OData API call.
6. Token is cached in memory and refreshed automatically before expiry.

### Python Library

`signxml` handles the enveloped XML signature with SHA-256 digest and Exclusive C14N. No manual XML manipulation needed.

### Required Credentials

| Variable | Description |
|---|---|
| `SF_BASE_URL` | SF API host, e.g. `https://api4.successfactors.com` |
| `SF_COMPANY_ID` | Your SF company/tenant ID |
| `SF_USER_ID` | Admin user ID used to authenticate |
| `SF_CLIENT_ID` | API key from SF provisioning |
| `SF_PRIVATE_KEY_PATH` | Path to X.509 private key PEM file for SAML signing |

---

## LLM Layer

LiteLLM provides a unified OpenAI-compatible interface to 100+ LLM providers. The agent code uses a single `litellm.completion()` call — switching providers is a config change only.

### Configuration

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | Provider name: `openai`, `anthropic`, `azure`, `ollama`, `gemini`, … |
| `LLM_MODEL` | Model name, e.g. `gpt-4o`, `claude-opus-4-7`, `llama3.2` |
| `LLM_API_KEY` | API key (leave blank for local Ollama) |
| `LLM_API_BASE` | Optional: custom endpoint for Azure or proxies |

### Examples

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

---

## OData Tool Design

SuccessFactors exposes 1000+ entity types via OData. Rather than generating one tool per entity (which would overflow the LLM's context window), the agent uses **6 general-purpose tools** that work with any entity dynamically.

### Tools

| Tool | Method | Purpose |
|---|---|---|
| `sf_list_entities()` | GET `/$metadata` | Discover all available entity sets |
| `sf_get_schema(entity_name)` | GET `/$metadata` | Get fields, types, and key properties for one entity |
| `sf_query(entity, filter?, select?, top?, skip?, expand?, orderby?)` | GET | Query records with full OData parameter support |
| `sf_create(entity_name, data)` | POST | Create a new record |
| `sf_update(entity_name, key, data)` | PATCH | Update specific fields on a record |
| `sf_delete(entity_name, key)` | DELETE | Delete a record by key |

### Key Design Decisions

- **`sf_get_schema` is called before `sf_query`** when the agent is unsure of field names. This prevents hallucinated field names in filters.
- **Composite keys** in `sf_update`/`sf_delete` follow OData conventions, e.g. `userId='U001',startDate=datetime'2024-01-01T00:00:00'`.
- **Pagination** is handled by passing `top` and `skip`. The agent decides when to paginate based on result counts.
- **No auto-confirmation** for deletes — the agent is instructed in the system prompt to summarise what it will delete before calling `sf_delete`.

### ReAct Loop

The agent runs a standard ReAct loop:

```
User message
    → Think: what do I need?
    → Call tool (e.g. sf_get_schema, then sf_query)
    → Observe result
    → Think: is this enough to answer?
    → Repeat or respond
```

Conversation history is maintained per session. The system prompt informs the agent it has full SF admin access and describes the 6 tools.

---

## Frontend — Chainlit

Chainlit is the browser chat UI. It handles:
- WebSocket-based real-time messaging
- Conversation history display
- Streaming token output from the LLM
- File/attachment rendering for large result sets

Entry point: `app.py`. The Chainlit `@cl.on_message` handler calls `agent.chat(session_id, message)`.

---

## Bot Integrations

Both bots are thin adapters — they extract the user message, call the same `agent.chat()` function, and send the reply back.

### Telegram

- Library: `python-telegram-bot` v21+
- **Local mode:** polling (no public URL needed, works out of the box)
- **Cloud mode:** webhook registered at startup; route mounted on Chainlit's built-in FastAPI app (same port 8000, path `/telegram/webhook`)
- Mode selected automatically: if `TELEGRAM_WEBHOOK_URL` is set in `.env`, webhook mode is used; otherwise polling.

### WhatsApp

Two options, selected by which credentials are present in `.env`:

| Option | When to use | Requirement |
|---|---|---|
| **Meta Cloud API** | Production / cloud | Public HTTPS URL for webhook verification |
| **Twilio sandbox** | Local testing | Twilio account + ngrok tunnel |

### Per-User Memory

Each user is identified by `platform:user_id` (e.g. `telegram:123456789`). An in-memory dict stores conversation history per user. Chainlit handles this automatically; the bot adapters replicate the same pattern.

---

## Deployment

### docker-compose.yml (outline)

```yaml
services:
  sf-agent:
    build: .
    ports:
      - "8000:8000"    # Chainlit UI + webhook routes (/telegram/webhook, /whatsapp/webhook)
    env_file: .env
    volumes:
      - ./certs:/app/certs:ro   # Mount private key
```

### Local

```bash
cp .env.example .env   # fill in credentials
docker compose up
# Chainlit: http://localhost:8000
# Telegram bot: polling mode (no extra setup)
```

### Cloud

```bash
docker compose up -d
# Point TELEGRAM_WEBHOOK_URL and WHATSAPP webhook to your public URL
```

---

## Dependencies

```
chainlit
litellm
signxml
lxml
httpx
python-telegram-bot>=21
python-dotenv
pyyaml
```

WhatsApp (choose one — `httpx` already covers Meta Cloud API):
```
twilio     # only needed for Twilio sandbox option
```

---

## Out of Scope

- Per-user authentication (all requests run as the configured SF admin)
- Fine-grained permission enforcement (SF API returns errors for unauthorized operations)
- Persistent conversation history across restarts (in-memory only for now)
- Multi-tenant SF support (single tenant per deployment)
