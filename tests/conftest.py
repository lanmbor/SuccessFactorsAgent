import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from config import Config


@pytest.fixture
def cfg() -> Config:
    return Config(
        SF_BASE_URL="https://test.successfactors.com",
        SF_COMPANY_ID="TESTCO",
        SF_USER_ID="admin",
        SF_CLIENT_ID="test-client-id",
        SF_PRIVATE_KEY_PATH="",
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-4o",
        LLM_API_KEY="sk-test",
        LLM_API_BASE="",
    )


@pytest.fixture
def rsa_key_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
