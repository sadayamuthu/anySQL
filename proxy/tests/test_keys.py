import os
import pytest
from pathlib import Path
from unittest.mock import patch


def test_keystore_roundtrip(tmp_path):
    """set() stores encrypted key; get() decrypts it."""
    from anysql_proxy.keys import KeyStore, _CONFIG_DIR, _SECRET_FILE, _KEYS_FILE
    # Redirect storage to tmp_path
    with patch("anysql_proxy.keys._CONFIG_DIR", tmp_path), \
         patch("anysql_proxy.keys._SECRET_FILE", tmp_path / ".secret"), \
         patch("anysql_proxy.keys._KEYS_FILE", tmp_path / "keys.toml"):
        ks = KeyStore()
        ks.set("openai", "sk-test-key-12345")
        result = ks.get("openai")
    assert result == "sk-test-key-12345"


def test_keystore_env_fallback(tmp_path):
    """get() falls back to env var when no stored key exists."""
    with patch("anysql_proxy.keys._CONFIG_DIR", tmp_path), \
         patch("anysql_proxy.keys._SECRET_FILE", tmp_path / ".secret"), \
         patch("anysql_proxy.keys._KEYS_FILE", tmp_path / "keys.toml"), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-from-env"}):
        from anysql_proxy.keys import KeyStore
        ks = KeyStore()
        result = ks.get("openai")
    assert result == "sk-from-env"


def test_keystore_missing_returns_none(tmp_path):
    """get() returns None when no stored key and no env var."""
    with patch("anysql_proxy.keys._CONFIG_DIR", tmp_path), \
         patch("anysql_proxy.keys._SECRET_FILE", tmp_path / ".secret"), \
         patch("anysql_proxy.keys._KEYS_FILE", tmp_path / "keys.toml"):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from anysql_proxy.keys import KeyStore
            ks = KeyStore()
            result = ks.get("openai")
    assert result is None
