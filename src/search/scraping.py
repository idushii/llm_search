"""
Модуль для скрапинга и поиска в интернете
"""
import os
import json
import asyncio
import aiohttp
import requests
import time
import hashlib
from pathlib import Path
from urllib.parse import quote

from src.core.config import (
    SEARCHXNG_BASIC_AUTH_LOGIN, 
    SEARCHXNG_BASIC_AUTH_PASSWORD,
    SEARCHXNG_INTERVAL,
    JINA_RPS,
    AITUNNEL_RPS,
    CACHE_DIR,
    DOCS_DIR
)
from src.core.constants import HTTP_OK
from src.core.utils import logger, generate_hash, create_directory

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


class SearchEngine:
    """
    Класс для поиска в интернете и скрапинга страниц
    """
    def __init__(self):
        # URL для поискового сервиса
        self.search_url = "https://searchxng.ai/api/v1/search"
        
        # Создаем объект для ограничения скорости запросов
        self.rate_limiter = RateLimiter()
        
        # Создаем базовые директории для кэша
        create_directory(CACHE_DIR)
        create_directory(DOCS_DIR)
        
    async def search_topic(self, query, session, max_results=10):
        """
        Выполняет поиск по запросу
        
        Args:
            query (str): Поисковый запрос
            session (aiohttp.ClientSession): Сессия для HTTP-запросов
            max_results (int): Максимальное количество результатов
            
        Returns:
            list: Список результатов поиска
        """
        try:
            # Ожидаем перед запросом в соответствии с ограничениями API
            await self.rate_limiter.wait("searchxng")
            
            # Формируем параметры запроса
            params = {
                "query": query,
                "max_results": max_results
            }
            
            # Делаем запрос с базовой аутентификацией
            auth = aiohttp.BasicAuth(SEARCHXNG_BASIC_AUTH_LOGIN, SEARCHXNG_BASIC_AUTH_PASSWORD)
            async with session.get(self.search_url, params=params, auth=auth) as response:
                if response.status == HTTP_OK:
                    result = await response.json()
                    logger.info(f"Найдено {len(result['results'])} результатов для запроса: {query}")
                    return result['results']
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка при поиске ({response.status}): {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Произошла ошибка при поиске: {e}")
            return []
    
    async def fetch_page_content(self, url, session):
        """
        Получает содержимое страницы по URL
        
        Args:
            url (str): URL страницы
            session (aiohttp.ClientSession): Сессия для HTTP-запросов
            
        Returns:
            str: Содержимое страницы или None в случае ошибки
        """
        try:
            # Генерируем хеш URL для кэширования
            url_hash = generate_hash(url)
            cache_path = os.path.join(DOCS_DIR, f"{url_hash}.html")
            
            # Проверяем, есть ли страница в кэше
            if os.path.exists(cache_path):
                logger.info(f"Загрузка страницы из кэша: {url}")
                with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
                    
            # Ожидаем перед запросом в соответствии с ограничениями API
            await self.rate_limiter.wait("jina")
            
            logger.info(f"Загрузка страницы: {url}")
            async with session.get(url, timeout=30) as response:
                if response.status == HTTP_OK:
                    content = await response.text()
                    
                    # Сохраняем страницу в кэш
                    with open(cache_path, "w", encoding="utf-8", errors="ignore") as f:
                        f.write(content)
                        
                    return content
                else:
                    logger.error(f"Ошибка при загрузке страницы {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {url}: {e}")
            return None
    
    async def process_search_queries(self, search_queries_dict, max_results_per_query=5, max_pages_per_query=3):
        """
        Обрабатывает поисковые запросы и собирает результаты
        
        Args:
            search_queries_dict (dict): Словарь с подзапросами и поисковыми запросами
            max_results_per_query (int): Максимальное количество результатов для каждого запроса
            max_pages_per_query (int): Максимальное количество страниц для загрузки для каждого запроса
            
        Returns:
            dict: Словарь с результатами поиска
        """
        results = {}
        
        async with aiohttp.ClientSession() as session:
            # Обрабатываем каждый подзапрос
            for subtopic, search_queries in search_queries_dict.items():
                logger.info(f"Обработка подзапроса: {subtopic}")
                
                subtopic_results = []
                
                # Для каждого поискового запроса в подзапросе
                for query in search_queries:
                    # Выполняем поиск
                    search_results = await self.search_topic(query, session, max_results=max_results_per_query)
                    
                    # Ограничиваем количество страниц для загрузки
                    pages_to_download = search_results[:max_pages_per_query]
                    
                    # Загружаем страницы
                    for result in pages_to_download:
                        url = result.get("url")
                        if url:
                            # Получаем содержимое страницы
                            content = await self.fetch_page_content(url, session)
                            
                            if content:
                                # Добавляем содержимое к результату
                                result["content"] = content
                                subtopic_results.append(result)
                
                # Сохраняем результаты для подзапроса
                results[subtopic] = subtopic_results
        
        return results
        
    def save_search_results_to_json(self, results, theme_name, cache_dir="cache"):
        """
        Сохраняет результаты поиска в JSON файл
        
        Args:
            results (dict): Словарь с результатами поиска
            theme_name (str): Название темы (для имени файла)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для результатов поиска
            search_results_dir = os.path.join(cache_dir, "search_results")
            create_directory(search_results_dir)
            
            # Генерируем имя файла
            file_path = os.path.join(search_results_dir, f"{theme_name}.json")
            
            # Подготавливаем результаты для сохранения
            # Исключаем полное содержимое страниц, чтобы не делать файл слишком большим
            simplified_results = {}
            for subtopic, subtopic_results in results.items():
                simplified_subtopic_results = []
                for result in subtopic_results:
                    # Копируем результат без содержимого страницы
                    simplified_result = result.copy()
                    if "content" in simplified_result:
                        # Сохраняем только первые 500 символов содержимого для предварительного просмотра
                        simplified_result["content_preview"] = simplified_result["content"][:500]
                        del simplified_result["content"]
                    simplified_subtopic_results.append(simplified_result)
                simplified_results[subtopic] = simplified_subtopic_results
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(simplified_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Результаты поиска сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении результатов поиска: {e}")
            return None

async def run_search(search_queries_dict, theme_name):
    """
    Запускает процесс поиска по поисковым запросам
    
    Args:
        search_queries_dict (dict): Словарь с подзапросами и поисковыми запросами
        theme_name (str): Название темы
        
    Returns:
        dict: Словарь с результатами поиска
    """
    search_engine = SearchEngine()
    results = await search_engine.process_search_queries(search_queries_dict)
    search_engine.save_search_results_to_json(results, theme_name)
    return results 