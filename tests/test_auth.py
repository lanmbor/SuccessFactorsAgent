# tests/test_auth.py
import pytest
from lxml import etree
from sf.auth import build_assertion

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
