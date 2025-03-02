"""
Модуль для планирования поисковых запросов
"""
import requests
import json
import os

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, SEARCH_QUERIES_PROMPT
from src.core.constants import QUERY_PREFIX
from src.core.utils import logger, extract_text_between_prefix

class SearchQueryPlanner:
    """
    Класс для планирования поисковых запросов с использованием LLM
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or AITUNNEL_API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_search_queries(self, subtopic, max_tokens=8000):
        """
        Генерирует поисковые запросы для подзапроса
        
        Args:
            subtopic (str): Подзапрос
            
        Returns:
            list: Список поисковых запросов
        """
        try:
            payload = {
                "model": AITUNNEL_MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": SEARCH_QUERIES_PROMPT
                    },
                    {
                        "role": "user",
                        "content": subtopic
                    }
                ]
            }
            
            response = requests.post(AITUNNEL_API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Извлекаем поисковые запросы из ответа
                search_queries = extract_text_between_prefix(content, QUERY_PREFIX)
                
                logger.info(f"Сгенерировано {len(search_queries)} поисковых запросов для подзапроса: {subtopic}")
                return search_queries
            else:
                logger.error(f"Ошибка при обращении к API: {response.status_code}")
                logger.error(response.text)
                return []
                
        except Exception as e:
            logger.error(f"Произошла ошибка при генерации поисковых запросов: {e}")
            return []

    def save_search_queries_to_file(self, subtopics_with_queries, theme_name, cache_dir="cache"):
        """
        Сохраняет поисковые запросы в файл
        
        Args:
            subtopics_with_queries (dict): Словарь, где ключи - подзапросы, а значения - списки поисковых запросов
            theme_name (str): Название темы (для имени файла)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для кэша, если она не существует
            search_queries_dir = os.path.join(cache_dir, "search_queries")
            os.makedirs(search_queries_dir, exist_ok=True)
            
            # Генерируем имя файла
            file_path = os.path.join(search_queries_dir, f"{theme_name}.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(subtopics_with_queries, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Поисковые запросы сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении поисковых запросов: {e}")
            return None

    def generate_all_search_queries(self, subtopics):
        """
        Генерирует поисковые запросы для всех подзапросов
        
        Args:
            subtopics (list): Список подзапросов
            
        Returns:
            dict: Словарь, где ключи - подзапросы, а значения - списки поисковых запросов
        """
        result = {}
        
        for subtopic in subtopics:
            search_queries = self.generate_search_queries(subtopic)
            if search_queries:
                result[subtopic] = search_queries
        
        return result 