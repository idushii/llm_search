"""
Модуль для планирования подзапросов
"""
import requests
import json
import os

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, SUBTOPICS_PROMPT
from src.core.constants import SUBTOPIC_PREFIX
from src.core.utils import logger, extract_text_between_prefix

class TopicPlanner:
    """
    Класс для планирования подзапросов с использованием LLM
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or AITUNNEL_API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_subtopics(self, query, max_tokens=2000):
        """
        Генерирует список подзапросов для основного запроса
        
        Args:
            query (str): Основной запрос пользователя
            
        Returns:
            list: Список подзапросов
        """
        try:
            payload = {
                "model": AITUNNEL_MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": SUBTOPICS_PROMPT
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ]
            }
            
            response = requests.post(AITUNNEL_API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Извлекаем подзапросы из ответа
                subtopics = extract_text_between_prefix(content, SUBTOPIC_PREFIX)
                
                logger.info(f"Сгенерировано {len(subtopics)} подзапросов")
                return subtopics
            else:
                logger.error(f"Ошибка при обращении к API: {response.status_code}")
                logger.error(response.text)
                return []
                
        except Exception as e:
            logger.error(f"Произошла ошибка при генерации подзапросов: {e}")
            return []

    def save_subtopics_to_file(self, subtopics, query, theme_name, cache_dir="cache"):
        """
        Сохраняет подзапросы в файл
        
        Args:
            subtopics (list): Список подзапросов
            query (str): Основной запрос
            theme_name (str): Название темы (для имени файла)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для кэша, если она не существует
            os.makedirs(cache_dir, exist_ok=True)
            
            # Генерируем имя файла
            file_path = os.path.join(cache_dir, f"subtopics_{theme_name}.md")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Подзапросы для поиска по теме: {query}\n\n")
                for i, subtopic in enumerate(subtopics, 1):
                    f.write(f"{i}. {subtopic}\n")
            
            logger.info(f"Подзапросы сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении подзапросов: {e}")
            return None 