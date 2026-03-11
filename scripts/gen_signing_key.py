"""Run inside python:3.11-slim container to generate and verify the signing key."""
import subprocess, sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "cryptography"])

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

key = Ed25519PrivateKey.generate()
pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

with open("/secrets/signing_key.pem", "wb") as f:
    f.write(pem)

# Verify round-trip immediately
with open("/secrets/signing_key.pem", "rb") as f:
    raw = f.read()

key2 = serialization.load_pem_private_key(raw, password=None)
assert isinstance(key2, Ed25519PrivateKey), "Wrong key type after round-trip"
print("OK: Ed25519 key generated, written, and verified")
