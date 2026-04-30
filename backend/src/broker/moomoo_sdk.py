from __future__ import annotations

from pathlib import Path

from moomoo import SysConfig


def configure_sdk_encryption(rsa_private_key_path: str) -> bool:
    rsa_path = Path(rsa_private_key_path).expanduser() if rsa_private_key_path else None
    if not rsa_path:
        SysConfig.enable_proto_encrypt(False)
        return False
    if not rsa_path.is_file():
        raise FileNotFoundError(f"Moomoo RSA private key not found: {rsa_path}")
    SysConfig.enable_proto_encrypt(True)
    SysConfig.set_init_rsa_file(str(rsa_path))
    return True
