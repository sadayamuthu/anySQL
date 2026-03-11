"""
Encrypted API key storage.

Keys are stored in ~/.anysql/keys.toml, encrypted with a machine-local
key derived from a randomly generated secret stored in ~/.anysql/.secret.
"""
import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
import tomli_w
from pathlib import Path
from cryptography.fernet import Fernet


_CONFIG_DIR = Path.home() / ".anysql"
_SECRET_FILE = _CONFIG_DIR / ".secret"
_KEYS_FILE = _CONFIG_DIR / "keys.toml"


class KeyStore:
    def __init__(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not _SECRET_FILE.exists():
            _SECRET_FILE.write_bytes(Fernet.generate_key())
            _SECRET_FILE.chmod(0o600)
        self._fernet = Fernet(_SECRET_FILE.read_bytes())

    def set(self, provider: str, api_key: str) -> None:
        keys = self._load()
        keys[provider] = self._fernet.encrypt(api_key.encode()).decode()
        _KEYS_FILE.write_text(tomli_w.dumps(keys))
        _KEYS_FILE.chmod(0o600)

    def get(self, provider: str) -> str | None:
        keys = self._load()
        encrypted = keys.get(provider)
        if not encrypted:
            return os.environ.get(f"{provider.upper()}_API_KEY")
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            return None

    def _load(self) -> dict:
        if not _KEYS_FILE.exists():
            return {}
        return tomllib.loads(_KEYS_FILE.read_text())
