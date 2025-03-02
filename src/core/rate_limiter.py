import time
from datetime import datetime, timedelta
import asyncio

from src.core.config import AITUNNEL_RPS, JINA_RPS, SEARCHXNG_INTERVAL
from src.core.utils import logger


class RateLimiter:
    """
    Класс для ограничения скорости запросов
    """
    def __init__(self):
        # Словарь с временем последнего запроса для каждого сервиса
        self.last_request_time = {
            "searchxng": 0,
            "jina": 0,
            "aitunnel": 0
        }
        
        # Интервалы между запросами в секундах для разных сервисов
        self.intervals = {
            "searchxng": SEARCHXNG_INTERVAL,  # Интервал для равномерного распределения по минуте
            "jina": 1.0 / JINA_RPS,  # Интервал для Jina (запросов в секунду)
            "aitunnel": 1.0 / AITUNNEL_RPS  # Интервал для Aitunnel (запросов в секунду)
        }
    
    async def wait(self, service):
        """
        Ожидает необходимое время перед следующим запросом к сервису
        
        Args:
            service (str): Название сервиса ("searchxng", "jina", "aitunnel")
        """
        if service not in self.intervals:
            logger.warning(f"Неизвестный сервис: {service}, лимитирование не применяется")
            return
            
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time[service]
        sleep_time = max(0, self.intervals[service] - time_since_last_request)
        
        if sleep_time > 0:
            logger.debug(f"Ожидание {sleep_time:.2f} сек перед запросом к {service}")
            await asyncio.sleep(sleep_time)
            
        self.last_request_time[service] = time.time()
