"""API key storage — full implementation in Task 10."""
import os

class KeyStore:
    def get(self, provider: str) -> str | None:
        return os.environ.get(f"{provider.upper()}_API_KEY")

    def set(self, provider: str, api_key: str) -> None:
        pass  # stub — full encryption in Task 10
