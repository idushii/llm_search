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
from urllib.parse import quote, urlencode

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
from src.core.rate_limiter import RateLimiter
from src.core.config import SEARCHXNG_API_URL

class SearchEngine:
    """
    Класс для поиска в интернете и скрапинга страниц
    """
    def __init__(self):
        # URL для поискового сервиса
        self.search_url = SEARCHXNG_API_URL
        
        # Создаем объект для ограничения скорости запросов
        self.rate_limiter = RateLimiter()
        
        # Создаем базовые директории для кэша
        create_directory(CACHE_DIR)
        create_directory(DOCS_DIR)
        
    async def search_topic(self, query, session, max_results=10, format="json"):
        """
        Выполняет поиск по запросу
        
        Args:
            query (str): Поисковый запрос
            session (aiohttp.ClientSession): Сессия для HTTP-запросов
            max_results (int): Максимальное количество результатов
            format (str): Формат результатов поиска (json, html)
            
        Returns:
            list: Список результатов поиска
        """
        try:
            # Ожидаем перед запросом в соответствии с ограничениями API
            await self.rate_limiter.wait("searchxng")
            
            # Формируем параметры запроса
            params = {
                "q": query,
                "format": format
            }
            
            link = self.search_url + "?" + urlencode(params)
            
            # Делаем запрос с базовой аутентификацией
            auth = aiohttp.BasicAuth(SEARCHXNG_BASIC_AUTH_LOGIN, SEARCHXNG_BASIC_AUTH_PASSWORD)
            async with session.get(link, auth=auth) as response:
                if response.status == HTTP_OK:
                    result = await response.json()
                    result_wrap = result['results'][:max_results]
                    logger.info(f"Найдено {len(result_wrap)} результатов для запроса: {query}")
                    return result_wrap
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка при поиске ({response.status}): {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Произошла ошибка при поиске: {e}")
            return []
    
    async def fetch_page_content(self, url, session):
        """
        Получает содержимое страницы по URL, используя сервис r.jina.ai для преобразования в Markdown
        
        Args:
            url (str): URL страницы
            session (aiohttp.ClientSession): Сессия для HTTP-запросов
            
        Returns:
            str: Содержимое страницы в формате Markdown или None в случае ошибки
        """
        try:
            # Генерируем хеш URL для кэширования
            url_hash = generate_hash(url)
            cache_path = os.path.join(DOCS_DIR, f"{url_hash}.md")
            
            # Проверяем, есть ли страница в кэше
            if os.path.exists(cache_path):
                logger.info(f"Загрузка страницы из кэша: {url}")
                with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            
            # URL для r.jina.ai API
            jina_url = f"https://r.jina.ai/{quote(url)}"
            
            # Ожидаем перед запросом в соответствии с ограничениями API
            await self.rate_limiter.wait("jina")
            
            logger.info(f"Загрузка и преобразование страницы через r.jina.ai: {url}")
            
            # Устанавливаем таймаут и заголовки
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml"
            }
            
            async with session.get(jina_url, headers=headers, timeout=timeout) as response:
                if response.status == HTTP_OK:
                    # r.jina.ai возвращает содержимое сразу в формате Markdown
                    markdown_content = await response.text()
                    
                    # Проверяем, что получен действительный Markdown-контент
                    if markdown_content and len(markdown_content) > 100:  # Минимальная длина для валидного контента
                        # Сохраняем Markdown в кэш
                        with open(cache_path, "w", encoding="utf-8", errors="ignore") as f:
                            f.write(markdown_content)
                        
                        return markdown_content
                    else:
                        logger.warning(f"Получен пустой или слишком короткий Markdown от r.jina.ai для {url}")
                else:
                    logger.error(f"Ошибка при обращении к r.jina.ai для {url}: {response.status}")
                    
                    # Попробуем запасной вариант - прямое скачивание и извлечение текста
                    try:
                        logger.info(f"Попытка прямого скачивания страницы: {url}")
                        # Повторно ожидаем, но уже не для jina
                        await asyncio.sleep(1)
                        
                        async with session.get(url, headers=headers, timeout=timeout) as direct_response:
                            if direct_response.status == HTTP_OK:
                                html_content = await direct_response.text()
                                
                                # Извлекаем текст и конвертируем в простой Markdown
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(html_content, 'html.parser')
                                
                                # Удаляем скрипты и стили
                                for script_or_style in soup(["script", "style"]):
                                    script_or_style.extract()
                                
                                # Получаем текст и форматируем его как простой Markdown
                                paragraphs = []
                                
                                # Обрабатываем заголовки
                                for i in range(1, 7):
                                    for header in soup.find_all(f'h{i}'):
                                        paragraphs.append(f"{'#' * i} {header.get_text().strip()}\n")
                                
                                # Обрабатываем параграфы
                                for p in soup.find_all('p'):
                                    paragraphs.append(f"{p.get_text().strip()}\n\n")
                                
                                # Обрабатываем списки
                                for ul in soup.find_all('ul'):
                                    for li in ul.find_all('li'):
                                        paragraphs.append(f"* {li.get_text().strip()}\n")
                                    paragraphs.append("\n")
                                
                                # Собираем Markdown
                                markdown_content = "".join(paragraphs)
                                
                                # Сохраняем Markdown в кэш
                                with open(cache_path, "w", encoding="utf-8", errors="ignore") as f:
                                    f.write(markdown_content)
                                
                                return markdown_content
                    except Exception as direct_error:
                        logger.error(f"Ошибка при прямом скачивании страницы {url}: {direct_error}")
                    
            return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {url}: {e}")
            return None
    
    async def process_search_queries(self, search_queries_dict, max_results_per_query=10, max_pages_per_query=3, format="json"):
        """
        Обрабатывает поисковые запросы и собирает результаты
        
        Args:
            search_queries_dict (dict): Словарь с подзапросами и поисковыми запросами
            max_results_per_query (int): Максимальное количество результатов для каждого запроса
            max_pages_per_query (int): Максимальное количество страниц для загрузки для каждого запроса
            format (str): Формат результатов поиска (json, html)
            
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
                    search_results = await self.search_topic(query, session, max_results=max_results_per_query, format=format)
                    
                    # На этом этапе мы только собираем результаты поиска без скрапинга
                    # Скрапинг будет выполнен позже только для топ-5 отранжированных результатов
                    for result in search_results:
                        subtopic_results.append(result)
                
                # Сохраняем результаты для подзапроса
                results[subtopic] = subtopic_results
        
        return results
    
    async def scrape_ranked_results(self, ranked_results):
        """
        Скрапит содержимое страниц для отранжированных результатов поиска
        
        Args:
            ranked_results (list): Список отранжированных результатов поиска
            
        Returns:
            list: Список отранжированных результатов с добавленным содержимым
        """
        print(f"\nПолучение содержимого для {len(ranked_results)} лучших результатов...")
        
        results_with_content = []
        
        async with aiohttp.ClientSession() as session:
            for i, result in enumerate(ranked_results, 1):
                url = result.get("url")
                title = result.get("title", "")
                
                if url:
                    print(f"[{i}/{len(ranked_results)}] Загрузка страницы: {title[:50]}...", end="\r")
                    
                    # Получаем содержимое страницы
                    content = await self.fetch_page_content(url, session)
                    
                    if content:
                        # Добавляем содержимое к результату
                        result_with_content = result.copy()
                        result_with_content["content"] = content
                        results_with_content.append(result_with_content)
                    else:
                        logger.warning(f"Не удалось получить содержимое для URL: {url}")
        
        print(f"\nПолучено содержимое для {len(results_with_content)} из {len(ranked_results)} результатов.")
        return results_with_content
        
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
            os.makedirs(search_results_dir, exist_ok=True)
            
            # Формируем имя файла
            file_path = os.path.join(search_results_dir, f"{theme_name}.json")
            
            # Подготавливаем данные для сохранения - удаляем большие поля
            filtered_results = {}
            
            for subtopic, subtopic_results in results.items():
                filtered_subtopic_results = []
                
                for result in subtopic_results:
                    # Создаем копию результата без контента
                    filtered_result = {k: v for k, v in result.items() if k != "content"}
                    filtered_subtopic_results.append(filtered_result)
                
                filtered_results[subtopic] = filtered_subtopic_results
            
            # Сохраняем данные в JSON формате
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(filtered_results, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Результаты поиска сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении результатов поиска: {e}")
            return None
    
    def save_scraped_content(self, ranked_results_with_content, theme_name, cache_dir="cache"):
        """
        Сохраняет скрапленное содержимое страниц в отдельные файлы
        
        Args:
            ranked_results_with_content (list): Список отранжированных результатов с содержимым
            theme_name (str): Название темы (для имени директории)
            cache_dir (str): Директория кэша
            
        Returns:
            bool: True, если сохранение прошло успешно, иначе False
        """
        try:
            # Создаем директорию для документов по теме
            theme_docs_dir = os.path.join(DOCS_DIR, theme_name)
            os.makedirs(theme_docs_dir, exist_ok=True)
            
            saved_count = 0
            
            for result in ranked_results_with_content:
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")
                
                if url and content:
                    # Генерируем хеш URL для имени файла
                    url_hash = generate_hash(url)
                    
                    # Формируем имя файла
                    file_name = f"{url_hash}.md"
                    file_path = os.path.join(theme_docs_dir, file_name)
                    
                    # Добавляем метаинформацию в начало документа
                    metadata = f"""---
title: {title}
url: {url}
date: {time.strftime("%Y-%m-%d %H:%M:%S")}
---

"""
                    
                    # Сохраняем содержимое с метаданными
                    with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
                        f.write(metadata + content)
                    
                    saved_count += 1
            
            logger.info(f"Сохранено {saved_count} документов по теме '{theme_name}' в {theme_docs_dir}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении скрапленного содержимого: {e}")
            return False


async def run_search(search_queries_dict, theme_name):
    """
    Выполняет поиск и обработку результатов
    
    Args:
        search_queries_dict (dict): Словарь с подзапросами и поисковыми запросами
        theme_name (str): Название темы для кэширования
        
    Returns:
        dict: Словарь с результатами поиска
    """
    search_engine = SearchEngine()
    
    # Выполняем поиск по всем запросам и получаем результаты
    search_results = await search_engine.process_search_queries(
        search_queries_dict,
        max_results_per_query=10,
        max_pages_per_query=5
    )
    
    # Сохраняем результаты поиска в JSON
    search_engine.save_search_results_to_json(search_results, theme_name)
    
    return search_results


async def scrape_top_ranked_results(ranked_results, theme_name):
    """
    Скрапит и сохраняет содержимое страниц для топ отранжированных результатов
    
    Args:
        ranked_results (list): Список отранжированных результатов
        theme_name (str): Название темы для кэширования
        
    Returns:
        list: Список отранжированных результатов с добавленным содержимым
    """
    search_engine = SearchEngine()
    
    # Скрапим содержимое для отранжированных результатов
    ranked_results_with_content = await search_engine.scrape_ranked_results(ranked_results)
    
    # Сохраняем скрапленное содержимое
    search_engine.save_scraped_content(ranked_results_with_content, theme_name)
    
    return ranked_results_with_content 