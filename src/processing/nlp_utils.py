"""
Модуль для генерации ответа на основе саммари
"""
import os
import requests
import json
import time

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS
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
    
    def generate_answer(self, query, summaries, theme_name=None):
        """
        Генерирует структурированный ответ на основе саммари
        
        Args:
            query (str): Исходный запрос пользователя
            summaries (list): Список отранжированных саммари
            theme_name (str, optional): Название темы для сохранения ответа
            
        Returns:
            str: Структурированный ответ
        """
        try:
            # Формируем контекст из саммари
            context = ""
            sources = []
            
            print("Формирование контекста из саммари для генерации ответа...")
            
            for i, summary_doc in enumerate(summaries):
                summary = summary_doc.get("summary", "")
                title = summary_doc.get("title", f"Источник {i+1}")
                url = summary_doc.get("url", "")
                
                if summary:
                    context += f"\nИСТОЧНИК {i+1}:\nЗаголовок: {title}\nURL: {url}\n\n{summary}\n\n"
                    sources.append(f"{i+1}. [{title}]({url})")
            
            # Формируем промпт для генерации ответа
            answer_prompt = f"""
            Ты – профессиональный аналитик, который создает структурированные, информативные ответы на основе предоставленных источников.
            
            Твоя задача – составить исчерпывающий ответ на запрос пользователя, основываясь ТОЛЬКО на предоставленных саммари источников.
            
            ЗАПРОС ПОЛЬЗОВАТЕЛЯ:
            {query}
            
            ПРЕДОСТАВЛЕННЫЕ ИСТОЧНИКИ:
            {context}
            
            ТРЕБОВАНИЯ К ОТВЕТУ:
            1. Начни с краткого введения, поясняющего суть вопроса
            2. Раздели ответ на логические разделы с подзаголовками
            3. Структурируй информацию от общего к частному
            4. В конце предоставь список использованных источников в формате Markdown
            5. Убедись, что весь ответ использует Markdown для форматирования
            6. Сосредоточься только на фактах из предоставленных источников, не добавляй собственную информацию
            
            ФОРМАТ ОТВЕТА:
            # Ответ на запрос: {query}
            
            ## Введение
            ...
            
            ## Основные разделы
            ...
            
            ## Заключение
            ...
            
            ## Использованные источники
            - [Название источника 1](URL1)
            - [Название источника 2](URL2)
            ...
            """
            
            print("Генерация итогового ответа...")
            
            # Ограничиваем частоту запросов к API
            time.sleep(1.0 / AITUNNEL_RPS)
            
            payload = {
                "model": AITUNNEL_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": answer_prompt
                    }
                ]
            }
            
            # Выполняем запрос к LLM API
            response = requests.post(AITUNNEL_API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                llm_response = response.json()
                answer = llm_response["choices"][0]["message"]["content"]
                
                # Добавляем список источников, если их нет в ответе
                if "## Использованные источники" not in answer:
                    answer += "\n\n## Использованные источники\n"
                    for source in sources:
                        answer += f"- {source}\n"
                
                print("Ответ успешно сгенерирован!")
                
                # Если указано имя темы, сохраняем ответ и запрос
                if theme_name:
                    self.save_answer_to_file(answer, query, theme_name)
                    self.save_request_to_file(query, theme_name)
                
                return answer
            else:
                logger.error(f"Ошибка при обращении к API: {response.status_code}")
                logger.error(response.text)
                return f"Не удалось сгенерировать ответ: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {e}")
            return f"Произошла ошибка при генерации ответа: {e}"
    
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