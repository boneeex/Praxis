"""Generate RS256 JWT keys for Praxis."""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

pems_dir = Path(__file__).resolve().parents[1] / "pems"
pems_dir.mkdir(exist_ok=True)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
(pems_dir / "private.pem").write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
)
(pems_dir / "public.pem").write_bytes(
    key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)
print(f"Keys written to {pems_dir}")
