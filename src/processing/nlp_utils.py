"""
Модуль для генерации ответа на основе полных текстов документов
"""
import os
import requests
import json
import time
import markdown
from bs4 import BeautifulSoup

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS
from src.core.constants import ANSWER_FILE
from src.core.utils import logger, create_directory

class AnswerGenerator:
    """
    Класс для генерации структурированного ответа на основе полных текстов документов
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or AITUNNEL_API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_answer(self, query, documents, theme_name=None):
        """
        Генерирует структурированный ответ на основе полных текстов документов
        
        Args:
            query (str): Исходный запрос пользователя
            documents (list): Список документов с полными текстами
            theme_name (str, optional): Название темы для сохранения ответа
            
        Returns:
            str: Структурированный ответ
        """
        try:
            # Формируем контекст из полных текстов документов
            context = ""
            sources = []
            
            print("Формирование контекста из полных текстов документов для генерации ответа...")
            
            for i, doc in enumerate(documents):
                content = doc.get("content", "")
                title = doc.get("title", f"Источник {i+1}")
                url = doc.get("url", "")
                
                if content:
                    # Для больших документов ограничиваем размер, чтобы не превышать лимиты API
                    max_content_length = 500000  # Примерное ограничение
                    if len(content) > max_content_length:
                        # Обрезаем контент, сохраняя начало и конец
                        half_length = max_content_length // 2
                        truncated_content = content[:half_length] + "\n\n[...содержимое сокращено...]\n\n" + content[-half_length:]
                        context += f"\nИСТОЧНИК {i+1}:\nЗаголовок: {title}\nURL: {url}\n\n{truncated_content}\n\n"
                    else:
                        context += f"\nИСТОЧНИК {i+1}:\nЗаголовок: {title}\nURL: {url}\n\n{content}\n\n"
                    
                    sources.append(f"{i+1}. [{title}]({url})")
            
            # Формируем промпт для генерации ответа
            answer_prompt = f"""
            Ты – профессиональный аналитик, который создает структурированные, информативные ответы на основе предоставленных источников.
            
            Твоя задача – составить исчерпывающий ответ на запрос пользователя, основываясь ТОЛЬКО на предоставленных полных текстах документов.
            
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
            7. Найди и проанализируй ключевые моменты из полных текстов документов
            8. Добавляй отметки о том, откуда была взята информация в формате: [Источник #1](URL1)
            
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
            
            print("Генерация итогового ответа на основе полных текстов документов...")
            
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
                
                # Если указано имя темы, сохраняем ответ в разных форматах
                if theme_name:
                    # Сохраняем Markdown версию
                    markdown_path = self.save_answer_to_file(answer, query, theme_name)
                    if markdown_path:
                        print(f"Markdown версия ответа сохранена в: {markdown_path}")
                    
                    # Сохраняем HTML версию
                    html_path = self.save_answer_to_html(answer, query, theme_name)
                    if html_path:
                        print(f"HTML версия ответа сохранена в: {html_path}")
                    
                    # Сохраняем запрос
                    request_path = self.save_request_to_file(query, theme_name)
                    if request_path:
                        print(f"Запрос сохранен в: {request_path}")
                
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

    def save_answer_to_html(self, answer, query, theme_name, cache_dir="cache"):
        """
        Сохраняет ответ в HTML формате
        
        Args:
            answer (str): Сгенерированный ответ в формате Markdown
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
            file_path = os.path.join(theme_dir, "answer.html")
            
            # Добавляем заголовок с запросом
            markdown_content = f"# Ответ на запрос: {query}\n\n{answer}"
            
            # Конвертируем Markdown в HTML с поддержкой таблиц
            html_content = markdown.markdown(markdown_content, extensions=['tables'])
            
            # Создаем красивый HTML с CSS стилями
            html_template = f"""
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Ответ на запрос: {query}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                        color: #333;
                    }}
                    h1 {{
                        color: #2c3e50;
                        border-bottom: 2px solid #eee;
                        padding-bottom: 10px;
                    }}
                    h2 {{
                        color: #34495e;
                        margin-top: 30px;
                    }}
                    p {{
                        margin-bottom: 15px;
                    }}
                    a {{
                        color: #3498db;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    ul, ol {{
                        margin-bottom: 15px;
                        padding-left: 20px;
                    }}
                    li {{
                        margin-bottom: 5px;
                    }}
                    code {{
                        background-color: #f8f9fa;
                        padding: 2px 5px;
                        border-radius: 3px;
                        font-family: monospace;
                    }}
                    pre {{
                        background-color: #f8f9fa;
                        padding: 15px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                    blockquote {{
                        border-left: 4px solid #ddd;
                        margin: 15px 0;
                        padding-left: 15px;
                        color: #666;
                    }}
                    /* Стили для таблиц */
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 15px 0;
                        background-color: #fff;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    }}
                    th, td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #f8f9fa;
                        font-weight: 600;
                        color: #2c3e50;
                    }}
                    tr:nth-child(even) {{
                        background-color: #f8f9fa;
                    }}
                    tr:hover {{
                        background-color: #f5f5f5;
                    }}
                    /* Адаптивность для таблиц */
                    @media screen and (max-width: 600px) {{
                        table {{
                            display: block;
                            overflow-x: auto;
                            white-space: nowrap;
                        }}
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_template)
            
            logger.info(f"HTML версия ответа сохранена в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении HTML версии ответа: {e}")
            return None 