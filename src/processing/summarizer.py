"""
Модуль для саммаризации документов
"""
import os
import requests
import json
from bs4 import BeautifulSoup
import re
import time

from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS, SUMMARIZATION_PROMPT, SUMMARIES_DIR
from src.core.utils import logger, generate_hash, create_directory, count_words

class DocumentSummarizer:
    """
    Класс для саммаризации документов
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or AITUNNEL_API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Создаем директорию для хранения саммари
        create_directory(SUMMARIES_DIR)
    
    def extract_text_from_html(self, html_content):
        """
        Извлекает текст из HTML-документа
        
        Args:
            html_content (str): HTML-содержимое документа
            
        Returns:
            str: Извлеченный текст
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Удаляем скрипты и стили
            for script_or_style in soup(["script", "style"]):
                script_or_style.extract()
            
            # Получаем текст
            text = soup.get_text()
            
            # Удаляем лишние пробелы и переносы строк
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            logger.error(f"Ошибка при извлечении текста из HTML: {e}")
            return ""
    
    def summarize_text(self, text, max_tokens=8000):
        """
        Генерирует саммари для текста
        
        Args:
            text (str): Исходный текст
            max_tokens (int): Максимальное количество токенов для обработки
            
        Returns:
            str: Саммари текста или None в случае ошибки
        """
        try:
            # Ограничиваем размер текста для API (примерно 1 токен = 4 символа)
            text = text[:max_tokens * 4]
            
            # Ограничиваем частоту запросов к API
            time.sleep(1.0 / AITUNNEL_RPS)
            
            payload = {
                "model": AITUNNEL_MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": SUMMARIZATION_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"Пожалуйста, сделай summary следующего текста:\n\n{text}"
                    }
                ]
            }
            
            response = requests.post(AITUNNEL_API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                summary = result["choices"][0]["message"]["content"]
                logger.info(f"Саммари успешно сгенерировано, длина: {len(summary)}")
                return summary
            else:
                logger.error(f"Ошибка при обращении к API: {response.status_code}")
                logger.error(response.text)
                return None
                
        except Exception as e:
            logger.error(f"Произошла ошибка при генерации саммари: {e}")
            return None
    
    def create_summary(self, content, title, url, original_query, theme_name):
        """
        Создает и сохраняет саммари для документа
        
        Args:
            content (str): Содержимое документа
            title (str): Заголовок документа
            url (str): URL документа
            original_query (str): Исходный запрос пользователя
            theme_name (str): Название темы для кэширования
            
        Returns:
            dict: Документ с саммари или None в случае ошибки
        """
        try:
            # Проверяем, есть ли у нас уже саммари для этого URL
            url_hash = generate_hash(url)
            summary_path = os.path.join(SUMMARIES_DIR, theme_name, f"{url_hash}.md")
            
            # Если саммари уже существует, загружаем его
            if os.path.exists(summary_path):
                logger.info(f"Загрузка существующего саммари для: {url}")
                with open(summary_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Извлекаем саммари из файла
                    summary_match = re.search(r"## Саммари\n\n(.*)", content, re.DOTALL)
                    if summary_match:
                        summary = summary_match.group(1)
                        return {
                            "title": title,
                            "url": url,
                            "summary": summary,
                            "query": original_query
                        }
            
            # Иначе создаем новое саммари
            logger.info(f"Создание нового саммари для: {title}")
            
            # Генерируем саммари
            summary = self.summarize_text(content)
            
            if not summary:
                logger.error(f"Не удалось создать саммари для: {url}")
                return None
            
            # Создаем документ с саммари
            document = {
                "title": title,
                "url": url,
                "summary": summary,
                "query": original_query
            }
            
            # Сохраняем саммари в файл
            self.save_summary_to_file(document, theme_name)
            
            return document
            
        except Exception as e:
            logger.error(f"Ошибка при создании саммари: {e}")
            return None
    
    def summarize_document(self, document):
        """
        Саммаризирует документ
        
        Args:
            document (dict): Документ для саммаризации (словарь с полями)
            
        Returns:
            dict: Обогащенный документ с саммари
        """
        try:
            url = document.get("url")
            content = document.get("content")
            
            if not content:
                logger.warning(f"Документ не содержит контента для саммаризации: {url}")
                return document
            
            # Извлекаем текст из HTML
            extracted_text = self.extract_text_from_html(content)
            
            if not extracted_text:
                logger.warning(f"Не удалось извлечь текст из документа: {url}")
                return document
            
            # Генерируем саммари
            summary = self.summarize_text(extracted_text)
            
            if summary:
                # Добавляем саммари к документу
                document_with_summary = document.copy()
                document_with_summary["summary"] = summary
                return document_with_summary
            else:
                logger.warning(f"Не удалось сгенерировать саммари для документа: {url}")
                return document
                
        except Exception as e:
            logger.error(f"Ошибка при саммаризации документа: {e}")
            return document
    
    def save_summary_to_file(self, document, theme_name, subtopic_name=None):
        """
        Сохраняет саммари документа в файл
        
        Args:
            document (dict): Документ с саммари
            theme_name (str): Название темы
            subtopic_name (str, optional): Название подзапроса
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            url = document.get("url")
            title = document.get("title", "Без заголовка")
            summary = document.get("summary")
            
            if not summary:
                logger.warning(f"Документ не содержит саммари для сохранения: {url}")
                return None
            
            # Создаем директорию для темы, если она не существует
            theme_dir = os.path.join(SUMMARIES_DIR, theme_name)
            create_directory(theme_dir)
            
            # Генерируем имя файла на основе URL
            url_hash = generate_hash(url)
            file_path = os.path.join(theme_dir, f"{url_hash}.md")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"URL: {url}\n\n")
                
                if subtopic_name:
                    f.write(f"Подзапрос: {subtopic_name}\n\n")
                
                f.write("## Саммари\n\n")
                f.write(summary)
            
            logger.info(f"Саммари сохранено в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении саммари: {e}")
            return None
    
    def process_documents(self, documents, theme_name):
        """
        Обрабатывает список документов: генерирует и сохраняет саммари
        
        Args:
            documents (list): Список документов для обработки
            theme_name (str): Название темы
            
        Returns:
            list: Список документов с саммари
        """
        documents_with_summaries = []
        
        for document in documents:
            # Проверяем, был ли документ уже обработан
            url = document.get("url")
            url_hash = generate_hash(url)
            file_path = os.path.join(SUMMARIES_DIR, theme_name, f"{url_hash}.md")
            
            if os.path.exists(file_path):
                logger.info(f"Саммари для документа уже существует: {url}")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Извлекаем саммари из файла
                    summary_match = re.search(r"## Саммари\n\n(.*)", content, re.DOTALL)
                    if summary_match:
                        summary = summary_match.group(1)
                        document_with_summary = document.copy()
                        document_with_summary["summary"] = summary
                        documents_with_summaries.append(document_with_summary)
                    else:
                        logger.warning(f"Не удалось извлечь саммари из файла: {file_path}")
                        documents_with_summaries.append(document)
            else:
                # Саммаризируем документ
                document_with_summary = self.summarize_document(document)
                
                # Сохраняем саммари
                subtopic = document.get("subtopic")
                self.save_summary_to_file(document_with_summary, theme_name, subtopic)
                
                documents_with_summaries.append(document_with_summary)
        
        return documents_with_summaries 