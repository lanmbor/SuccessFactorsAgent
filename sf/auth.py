# sf/auth.py
import asyncio
import uuid
import base64
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from lxml import etree
from signxml import XMLSigner
from signxml.algorithms import SignatureConstructionMethod
from config import Config

SAML = "urn:oasis:names:tc:SAML:2.0:assertion"
BEARER = "urn:oasis:names:tc:SAML:2.0:cm:bearer"
PASSWORD_CLASS = "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"


def build_assertion(config: Config) -> tuple[etree._Element, str]:
    assertion_id = "_" + uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    token_url = f"{config.SF_BASE_URL}/oauth/token"

    assertion = etree.Element(
        f"{{{SAML}}}Assertion",
        attrib={
            "ID": assertion_id,
            "Version": "2.0",
            "IssueInstant": now.strftime(fmt),
        },
        nsmap={"saml": SAML},
    )

    issuer = etree.SubElement(assertion, f"{{{SAML}}}Issuer")
    issuer.text = config.SF_CLIENT_ID

    subject = etree.SubElement(assertion, f"{{{SAML}}}Subject")
    name_id = etree.SubElement(subject, f"{{{SAML}}}NameID")
    name_id.text = f"{config.SF_USER_ID}@{config.SF_COMPANY_ID}"
    etree.SubElement(subject, f"{{{SAML}}}SubjectConfirmation", attrib={"Method": BEARER})

    conditions = etree.SubElement(
        assertion,
        f"{{{SAML}}}Conditions",
        attrib={
            "NotBefore": (now - timedelta(minutes=5)).strftime(fmt),
            "NotOnOrAfter": (now + timedelta(hours=1)).strftime(fmt),
        },
    )
    audience_restriction = etree.SubElement(conditions, f"{{{SAML}}}AudienceRestriction")
    audience = etree.SubElement(audience_restriction, f"{{{SAML}}}Audience")
    audience.text = token_url

    authn_stmt = etree.SubElement(
        assertion,
        f"{{{SAML}}}AuthnStatement",
        attrib={"AuthnInstant": now.strftime(fmt)},
    )
    authn_ctx = etree.SubElement(authn_stmt, f"{{{SAML}}}AuthnContext")
    authn_ctx_ref = etree.SubElement(authn_ctx, f"{{{SAML}}}AuthnContextClassRef")
    authn_ctx_ref.text = PASSWORD_CLASS

    return assertion, assertion_id


def sign_assertion(
    assertion: etree._Element, assertion_id: str, private_key_pem: bytes
) -> str:
    signer = XMLSigner(
        method=SignatureConstructionMethod.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    )
    signed = signer.sign(assertion, key=private_key_pem, reference_uri=f"#{assertion_id}")
    return etree.tostring(signed, encoding="unicode")


async def exchange_token(config: Config, signed_xml: str) -> tuple[str, datetime]:
    assertion_b64 = base64.b64encode(signed_xml.encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{config.SF_BASE_URL}/oauth/token",
            data={
                "client_id": config.SF_CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:saml2-bearer",
                "assertion": assertion_b64,
                "company_id": config.SF_COMPANY_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 43200))
        return data["access_token"], expires_at


class SFAuth:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._private_key_pem: bytes = Path(config.SF_PRIVATE_KEY_PATH).read_bytes()
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._token and self._expires_at:
                if datetime.now(timezone.utc) < self._expires_at - timedelta(minutes=5):
                    return self._token
            assertion, assertion_id = build_assertion(self._config)
            signed_xml = sign_assertion(assertion, assertion_id, self._private_key_pem)
            self._token, self._expires_at = await exchange_token(self._config, signed_xml)
            return self._token
