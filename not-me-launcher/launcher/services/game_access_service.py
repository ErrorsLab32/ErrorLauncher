from __future__ import annotations

import os
import requests

from launcher.config import GitHubConfig
from launcher.services.access_token_store import AccessTokenStore


class GameAccessError(Exception):
    pass


class GameAccessService:
    REPOSITORY = "ErrorsLab32/Not-ME"
    API_ROOT = "https://api.github.com"

    def __init__(self, store: AccessTokenStore, session: requests.Session | None = None) -> None:
        self._store, self._session = store, session or requests.Session()

    def config(self) -> GitHubConfig | None:
        token = os.getenv("GITHUB_TOKEN", "").strip() or self._store.load()
        return GitHubConfig(self.REPOSITORY, token) if token else None

    def validate_and_save(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise GameAccessError("Введите код доступа.")
        try:
            response = self._session.get(f"{self.API_ROOT}/repos/{self.REPOSITORY}", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=(10, 30))
        except requests.RequestException as error:
            raise GameAccessError("Не удалось проверить код доступа. Проверьте соединение.") from error
        if response.status_code in (401, 403):
            raise GameAccessError("Код доступа недействителен или не даёт доступ к тестовой сборке.")
        if response.status_code >= 400:
            raise GameAccessError(f"Не удалось проверить код доступа (HTTP {response.status_code}).")
        self._store.save(token)

    def forget_invalid_token(self) -> None:
        self._store.delete()
