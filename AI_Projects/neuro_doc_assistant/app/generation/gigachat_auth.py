"""
@file: gigachat_auth.py
@description: GigaChat OAuth 2.0 аутентификация
@dependencies: requests, os, uuid, time
@created: 2024-12-22
"""

import os
import uuid
import time
import requests
from typing import Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


class GigaChatAuth:
    """
    Класс для OAuth 2.0 аутентификации в GigaChat API.
    
    Отвечает за:
    - Получение access token через OAuth 2.0
    - Кэширование токена (действителен 30 минут)
    - Автоматическое обновление токена перед истечением
    """
    
    # Официальные endpoints GigaChat API
    OAUTH_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    API_BASE_URL = "https://gigachat.devices.sberbank.ru/api/v1"
    
    def __init__(
        self,
        auth_key: Optional[str] = None,
        scope: Optional[str] = None
    ):
        """
        Инициализация GigaChatAuth.
        
        Args:
            auth_key: Base64 encoded "Client ID:Client Secret" (если None, берётся из GIGACHAT_AUTH_KEY)
            scope: Scope для OAuth (GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP)
                  Если None, берётся из GIGACHAT_SCOPE или используется GIGACHAT_API_PERS по умолчанию
        """
        self.auth_key = auth_key or os.getenv("GIGACHAT_AUTH_KEY")
        self.scope = scope or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        
        # Кэш токена
        self._access_token_cache: Optional[str] = None
        self._token_expires_at: float = 0
        
        # Настройка сессии с отключенной проверкой SSL для OAuth endpoint
        # (требуется из-за самоподписанного сертификата)
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Отключаем проверку SSL для OAuth endpoint
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def get_access_token(self) -> Optional[str]:
        """
        Получает access token для GigaChat API.
        Использует кэш, если токен ещё действителен.
        
        Returns:
            Access token или None при ошибке
        """
        # Проверяем кэш токена (действителен 30 минут)
        current_time = time.time()
        if self._access_token_cache and current_time < self._token_expires_at - 60:
            # Токен ещё действителен (обновляем за минуту до истечения)
            return self._access_token_cache
        
        # Получаем новый токен
        return self._request_new_token()
    
    def _request_new_token(self) -> Optional[str]:
        """
        Запрашивает новый access token через OAuth 2.0.
        
        Returns:
            Access token или None при ошибке
        """
        if not self.auth_key:
            return None
        
        # Генерируем уникальный идентификатор запроса (UUID4)
        rq_uid = str(uuid.uuid4())
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": rq_uid,
            "Authorization": f"Basic {self.auth_key}"
        }
        
        data = {
            "scope": self.scope
        }
        
        try:
            response = self.session.post(
                self.OAUTH_TOKEN_URL,
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                access_token = response_data.get("access_token")
                
                if access_token:
                    # Сохраняем токен в кэш
                    self._access_token_cache = access_token
                    
                    # expires_at в миллисекундах, конвертируем в секунды
                    expires_at_ms = response_data.get("expires_at", 0)
                    if expires_at_ms > 1000000000000:  # Это миллисекунды
                        self._token_expires_at = expires_at_ms / 1000
                    else:  # Это уже секунды
                        self._token_expires_at = expires_at_ms
                    
                    return access_token
            else:
                # Логируем ошибку, но не прерываем работу
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Ошибка получения токена GigaChat API (статус {response.status_code}): "
                    f"{response.text[:500]}"
                )
                return None
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Исключение при получении токена GigaChat API: {e}")
            return None
    
    def invalidate_token(self):
        """Инвалидирует кэш токена (принудительное обновление)"""
        self._access_token_cache = None
        self._token_expires_at = 0

