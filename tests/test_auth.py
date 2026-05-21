# tests/test_auth.py
import base64
import urllib.parse
import pytest
import respx
import httpx
from datetime import datetime, timezone, timedelta
from lxml import etree
from sf.auth import build_assertion, sign_assertion, SFAuth, exchange_token

SAML = "urn:oasis:names:tc:SAML:2.0:assertion"


def test_build_assertion_issuer(cfg):
    assertion, _ = build_assertion(cfg)
    issuer = assertion.find(f"{{{SAML}}}Issuer")
    assert issuer is not None
    assert issuer.text == "test-client-id"


def test_build_assertion_subject_name_id(cfg):
    assertion, _ = build_assertion(cfg)
    name_id = assertion.find(f".//{{{SAML}}}NameID")
    assert name_id is not None
    assert name_id.text == "admin@TESTCO"


def test_build_assertion_audience_is_token_url(cfg):
    assertion, _ = build_assertion(cfg)
    audience = assertion.find(f".//{{{SAML}}}Audience")
    assert audience is not None
    assert audience.text == "https://test.successfactors.com/oauth/token"


def test_build_assertion_id_is_unique(cfg):
    _, id1 = build_assertion(cfg)
    _, id2 = build_assertion(cfg)
    assert id1 != id2


def test_build_assertion_conditions_has_not_before(cfg):
    assertion, _ = build_assertion(cfg)
    conditions = assertion.find(f"{{{SAML}}}Conditions")
    assert conditions is not None
    assert conditions.get("NotBefore") is not None
    assert conditions.get("NotOnOrAfter") is not None


DS = "http://www.w3.org/2000/09/xmldsig#"


def test_sign_assertion_inserts_signature_element(cfg, rsa_key_pem):
    assertion, assertion_id = build_assertion(cfg)
    signed_xml = sign_assertion(assertion, assertion_id, rsa_key_pem)
    root = etree.fromstring(signed_xml.encode())
    sig = root.find(f".//{{{DS}}}Signature")
    assert sig is not None


def test_sign_assertion_uses_rsa_sha256(cfg, rsa_key_pem):
    assertion, assertion_id = build_assertion(cfg)
    signed_xml = sign_assertion(assertion, assertion_id, rsa_key_pem)
    root = etree.fromstring(signed_xml.encode())
    sig_method = root.find(f".//{{{DS}}}SignatureMethod")
    assert sig_method is not None
    assert "rsa-sha256" in sig_method.get("Algorithm", "")


def test_sign_assertion_uses_exclusive_c14n(cfg, rsa_key_pem):
    assertion, assertion_id = build_assertion(cfg)
    signed_xml = sign_assertion(assertion, assertion_id, rsa_key_pem)
    root = etree.fromstring(signed_xml.encode())
    c14n = root.find(f".//{{{DS}}}CanonicalizationMethod")
    assert c14n is not None
    assert c14n.get("Algorithm") == "http://www.w3.org/2001/10/xml-exc-c14n#"


def test_sign_assertion_uses_sha256_digest(cfg, rsa_key_pem):
    assertion, assertion_id = build_assertion(cfg)
    signed_xml = sign_assertion(assertion, assertion_id, rsa_key_pem)
    root = etree.fromstring(signed_xml.encode())
    digest = root.find(f".//{{{DS}}}DigestMethod")
    assert digest is not None
    assert "sha256" in digest.get("Algorithm", "")


def test_sign_assertion_returns_string(cfg, rsa_key_pem):
    assertion, assertion_id = build_assertion(cfg)
    result = sign_assertion(assertion, assertion_id, rsa_key_pem)
    assert isinstance(result, str)
    assert result.startswith("<")


@pytest.fixture
def auth_with_key(cfg, rsa_key_pem, tmp_path):
    key_file = tmp_path / "test.pem"
    key_file.write_bytes(rsa_key_pem)
    cfg.SF_PRIVATE_KEY_PATH = str(key_file)
    return SFAuth(cfg)


@pytest.mark.asyncio
async def test_get_token_returns_access_token(auth_with_key):
    with respx.mock:
        respx.post("https://test.successfactors.com/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 43200})
        )
        token = await auth_with_key.get_token()
    assert token == "tok123"


@pytest.mark.asyncio
async def test_get_token_caches_result(auth_with_key):
    with respx.mock:
        route = respx.post("https://test.successfactors.com/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 43200})
        )
        await auth_with_key.get_token()
        await auth_with_key.get_token()
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_get_token_refreshes_when_expired(auth_with_key):
    with respx.mock:
        route = respx.post("https://test.successfactors.com/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok_new", "expires_in": 43200})
        )
        auth_with_key._token = "tok_old"
        auth_with_key._expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        token = await auth_with_key.get_token()
    assert token == "tok_new"
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_exchange_token_posts_correct_fields(cfg):
    signed_xml = "<saml>test-xml</saml>"
    expected_assertion = base64.b64encode(signed_xml.encode()).decode()

    with respx.mock:
        route = respx.post("https://test.successfactors.com/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok_exchange", "expires_in": 43200})
        )
        result = await exchange_token(cfg, signed_xml)

    # Verify the request was made once
    assert route.call_count == 1

    # Inspect the posted form data
    request = route.calls[0].request
    body = request.content.decode()
    form_fields = dict(pair.split("=", 1) for pair in body.split("&"))

    decoded_fields = {k: urllib.parse.unquote_plus(v) for k, v in form_fields.items()}

    assert decoded_fields["grant_type"] == "urn:ietf:params:oauth:grant-type:saml2-bearer"
    assert decoded_fields["assertion"] == expected_assertion

    # Verify the return value is a tuple of (str, datetime)
    assert isinstance(result, tuple)
    assert len(result) == 2
    access_token, expires_at = result
    assert isinstance(access_token, str)
    assert access_token == "tok_exchange"
    assert isinstance(expires_at, datetime)
