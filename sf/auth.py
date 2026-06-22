# sf/auth.py
import asyncio
import uuid
import base64
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from lxml import etree
from signxml import XMLSigner, methods
from config import Config


def build_assertion(config: Config) -> str:
    now = datetime.now(timezone.utc)
    not_after = now + timedelta(minutes=5)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    assertion_id = "_" + str(uuid.uuid4())
    token_url = f"{config.SF_BASE_URL}/oauth/token"

    saml_xml = f"""<saml2:Assertion xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion"
      ID="{assertion_id}" IssueInstant="{now.strftime(fmt)}" Version="2.0">
      <saml2:Issuer>{config.SF_CLIENT_ID}</saml2:Issuer>
      <saml2:Subject>
        <saml2:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified">{config.SF_USER_ID}</saml2:NameID>
        <saml2:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
          <saml2:SubjectConfirmationData NotOnOrAfter="{not_after.strftime(fmt)}" Recipient="{token_url}"/>
        </saml2:SubjectConfirmation>
      </saml2:Subject>
      <saml2:Conditions NotBefore="{now.strftime(fmt)}" NotOnOrAfter="{not_after.strftime(fmt)}">
        <saml2:AudienceRestriction><saml2:Audience>{token_url}</saml2:Audience></saml2:AudienceRestriction>
      </saml2:Conditions>
      <saml2:AuthnStatement AuthnInstant="{now.strftime(fmt)}">
        <saml2:AuthnContext>
          <saml2:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified</saml2:AuthnContextClassRef>
        </saml2:AuthnContext>
      </saml2:AuthnStatement>
      <saml2:AttributeStatement>
        <saml2:Attribute Name="client_id">
          <saml2:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:type="xs:string">{config.SF_CLIENT_ID}</saml2:AttributeValue>
        </saml2:Attribute>
      </saml2:AttributeStatement>
    </saml2:Assertion>"""

    return saml_xml


def sign_assertion(saml_xml: str, private_key_pem: bytes, certificate_pem: bytes) -> str:
    root = etree.fromstring(saml_xml.encode())
    signer = XMLSigner(
        method=methods.enveloped,
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    )
    signed_root = signer.sign(root, key=private_key_pem, cert=certificate_pem)
    return base64.b64encode(etree.tostring(signed_root, xml_declaration=False)).decode()


async def exchange_token(config: Config, assertion_b64: str) -> tuple[str, datetime]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
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
        self._private_key_pem: bytes | None = None
        self._certificate_pem: bytes | None = None
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._token and self._expires_at:
                if datetime.now(timezone.utc) < self._expires_at - timedelta(minutes=5):
                    return self._token
            if self._private_key_pem is None:
                self._private_key_pem = Path(self._config.SF_PRIVATE_KEY_PATH).read_bytes()
            if self._certificate_pem is None:
                self._certificate_pem = Path(self._config.SF_CERTIFICATE_PATH).read_bytes()
            saml_xml = build_assertion(self._config)
            assertion_b64 = sign_assertion(saml_xml, self._private_key_pem, self._certificate_pem)
            self._token, self._expires_at = await exchange_token(self._config, assertion_b64)
            return self._token
