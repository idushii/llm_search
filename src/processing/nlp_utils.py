"""
Модуль для генерации ответа на основе саммари
"""
import os
import requests
import json

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL
from src.core.constants import ANSWER_FILE
from src.core.utils import logger, create_directory

class AnswerGenerator:
    """
    Класс для генерации структурированного ответа на основе саммари
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or AITUNNEL_API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_answer(self, top_summaries, original_query):
        """
        Генерирует структурированный ответ на основе топ саммари
        
        Args:
            top_summaries (list): Список отранжированных саммари
            original_query (str): Исходный запрос пользователя
            
        Returns:
            str: Структурированный ответ на запрос или None в случае ошибки
        """
        try:
            # Формируем контекст из саммари
            context = ""
            for i, summary_doc in enumerate(top_summaries, 1):
                title = summary_doc.get("title", "Без заголовка")
                url = summary_doc.get("url", "")
                summary = summary_doc.get("summary", "")
                
                context += f"### Документ {i}: {title}\n"
                context += f"Источник: {url}\n\n"
                context += f"{summary}\n\n"
            
            # Формируем запрос к API
            prompt = f"""
На основе приведенных ниже саммари документов, составь структурированный и информативный ответ на следующий запрос:

ЗАПРОС: {original_query}

КОНТЕКСТ:
{context}

Требования к ответу:
1. Структурированный и логичный текст, разделенный на разделы и подразделы (с использованием заголовков Markdown)
2. Включение всей ключевой информации из предоставленных саммари
3. Отсутствие дублирования информации
4. Объективность и фактографичность
5. Добавление в конце списка источников информации с указанием URL (использованные документы)

Формат ответа должен быть в Markdown.
"""
            
            payload = {
                "model": AITUNNEL_MODEL,
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = requests.post(AITUNNEL_API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                logger.info(f"Ответ успешно сгенерирован, длина: {len(answer)}")
                return answer
            else:
                logger.error(f"Ошибка при обращении к API: {response.status_code}")
                logger.error(response.text)
                return None
                
        except Exception as e:
            logger.error(f"Произошла ошибка при генерации ответа: {e}")
            return None
    
    def save_answer_to_file(self, answer, query, theme_name, cache_dir="cache"):
        """
        Сохраняет ответ в файл
        
        Args:
            answer (str): Сгенерированный ответ
            query (str): Исходный запрос пользователя
            theme_name (str): Название темы (для имени каталога)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для темы, если она не существует
            theme_dir = os.path.join(cache_dir, theme_name)
            create_directory(theme_dir)
            
            # Генерируем имя файла
            file_path = os.path.join(theme_dir, ANSWER_FILE)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Ответ на запрос: {query}\n\n")
                f.write(answer)
            
            logger.info(f"Ответ сохранен в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении ответа: {e}")
            return None

    def save_request_to_file(self, query, theme_name, cache_dir="cache"):
        """
        Сохраняет исходный запрос в файл
        
        Args:
            query (str): Исходный запрос пользователя
            theme_name (str): Название темы (для имени каталога)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для темы, если она не существует
            theme_dir = os.path.join(cache_dir, theme_name)
            create_directory(theme_dir)
            
            # Генерируем имя файла
            file_path = os.path.join(theme_dir, "request.md")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Запрос\n\n")
                f.write(query)
            
            logger.info(f"Запрос сохранен в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении запроса: {e}")
            return None 