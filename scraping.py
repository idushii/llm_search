import os
import json
import asyncio
import aiohttp
import requests
import time
import hashlib
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

BASIC_AUTH_LOGIN = os.getenv("SEARCHXNG_BASIC_AUTH_LOGIN")
BASIC_AUTH_PASSWORD = os.getenv("SEARCHXNG_BASIC_AUTH_PASSWORD")

# Получаем лимиты запросов из переменных окружения
# Если переменная не задана, используем значения по умолчанию из ТЗ
# SearchXNg: 10 запросов в минуту с равным интервалом
SEARCHXNG_RPM = int(os.getenv("LIMIT_SEARCHXNG_RPM", "10"))  # Запросов в минуту
SEARCHXNG_INTERVAL = 60.0 / SEARCHXNG_RPM  # Интервал между запросами в секундах

# Jina и Aitunnel: запросов в секунду
JINA_RPS = float(os.getenv("LIMIT_JINA_RPS", "5"))  # 5 запросов в секунду
AITUNNEL_RPS = float(os.getenv("LIMIT_AITUNNEL_RPS", "2"))  # 2 запроса в секунду

# Создаем директорию для кэширования результатов поиска
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

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
        
        # Семафоры для ограничения одновременных запросов
        self.semaphores = {
            "searchxng": asyncio.Semaphore(1),  # Для SearchXNg используем строгое последовательное выполнение
            "jina": asyncio.Semaphore(int(JINA_RPS)),
            "aitunnel": asyncio.Semaphore(int(AITUNNEL_RPS))
        }
    
    async def wait(self, service):
        """
        Ожидает, если необходимо, чтобы соблюсти ограничение скорости запросов
        
        Args:
            service (str): Название сервиса ('searchxng', 'jina', 'aitunnel')
        """
        async with self.semaphores[service]:
            current_time = time.time()
            elapsed = current_time - self.last_request_time[service]
            
            if elapsed < self.intervals[service]:
                # Если с момента последнего запроса прошло меньше времени, чем необходимый интервал,
                # ожидаем оставшееся время
                wait_time = self.intervals[service] - elapsed
                await asyncio.sleep(wait_time)
            
            # Обновляем время последнего запроса
            self.last_request_time[service] = time.time()

class SearchEngine:
    """
    Класс для выполнения поисковых запросов через SearchXNg и обработки результатов
    """
    def __init__(self):
        # URL для поискового сервиса
        self.search_url = "https://searxng.ro.logging.network"
        # URL для сервиса парсинга содержимого страниц
        self.parser_url = "https://r.jina.ai/"
        # Создаем экземпляр ограничителя скорости запросов
        self.rate_limiter = RateLimiter()
    
    async def search_topic(self, topic, session, max_results=10):
        """
        Выполняет поисковый запрос по заданной теме
        
        Args:
            topic (str): Тема для поиска
            session (aiohttp.ClientSession): Сессия для выполнения HTTP запросов
            max_results (int): Максимальное количество результатов
            
        Returns:
            dict: Результаты поиска
        """
        try:
            # Ожидаем, соблюдая ограничение скорости запросов
            await self.rate_limiter.wait("searchxng")
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "q": topic,
                "language": "all",
                "format": "json"
            }
            
            async with session.get(self.search_url, headers=headers, params=payload, auth=aiohttp.BasicAuth(BASIC_AUTH_LOGIN, BASIC_AUTH_PASSWORD)) as response:
                if response.status == 200:
                    search_results = await response.json()
                    return {
                        "topic": topic,
                        "results": search_results.get("results", [])[:max_results]
                    }
                else:
                    print(f"Ошибка при поиске темы '{topic}': {response.status}")
                    return {"topic": topic, "results": []}
        except Exception as e:
            print(f"Произошла ошибка при поиске темы '{topic}': {e}")
            return {"topic": topic, "results": []}
    
    async def fetch_page_content(self, url, session):
        """
        Получает содержимое страницы через сервис парсинга
        
        Args:
            url (str): URL страницы для парсинга
            session (aiohttp.ClientSession): Сессия для выполнения HTTP запросов
            
        Returns:
            str: Содержимое страницы в формате Markdown
        """
        try:
            # Ожидаем, соблюдая ограничение скорости запросов
            await self.rate_limiter.wait("jina")
            
            encoded_url = quote(url, safe='')
            parser_url = f"{self.parser_url}{encoded_url}"
            
            async with session.get(parser_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"Ошибка при парсинге страницы '{url}': {response.status}")
                    return ""
        except Exception as e:
            print(f"Произошла ошибка при парсинге страницы '{url}': {e}")
            return ""
    
    async def process_search_results(self, topics, max_results_per_topic=5, max_pages_per_topic=3):
        """
        Выполняет поиск по нескольким темам и получает содержимое найденных страниц
        
        Args:
            topics (list): Список тем для поиска
            max_results_per_topic (int): Максимальное количество результатов для каждой темы
            max_pages_per_topic (int): Максимальное количество страниц для парсинга по каждой теме
            
        Returns:
            dict: Структурированные результаты поиска
        """
        # Создаем Throttled ClientSession для управления скоростью запросов
        conn = aiohttp.TCPConnector(limit=10)  # Ограничиваем количество одновременных соединений
        async with aiohttp.ClientSession(connector=conn) as session:
            # Выполняем поиск по всем темам с учетом лимитов запросов
            search_tasks = [self.search_topic(topic, session, max_results_per_topic) for topic in topics]
            search_results = await asyncio.gather(*search_tasks)
            
            all_results = {}
            
            # Обрабатываем результаты поиска и получаем содержимое страниц
            for result in search_results:
                topic = result["topic"]
                pages = result["results"]
                
                if not pages:
                    all_results[topic] = {"pages": []}
                    continue
                
                # Ограничиваем количество страниц для парсинга
                pages_to_process = pages[:max_pages_per_topic]
                
                # Получаем содержимое каждой страницы с учетом лимитов запросов
                content_tasks = [self.fetch_page_content(page["url"], session) for page in pages_to_process]
                page_contents = await asyncio.gather(*content_tasks)
                
                processed_pages = []
                for i, (page, content) in enumerate(zip(pages_to_process, page_contents)):
                    if content:
                        # Генерируем уникальный идентификатор для файла кэша
                        page_url = page.get("url", "")
                        page_hash = hashlib.md5(page_url.encode('utf-8')).hexdigest()
                        cache_file = CACHE_DIR / f"{page_hash}.md"
                        
                        # Сохраняем содержимое страницы в кэш
                        with open(cache_file, "w", encoding="utf-8") as f:
                            f.write(f"# {page.get('title', f'Страница {i+1}')}\n\n")
                            f.write(f"URL: {page_url}\n\n")
                            f.write(content)
                        
                        processed_pages.append({
                            "title": page.get("title", f"Страница {i+1}"),
                            "url": page_url,
                            "content_file": str(cache_file),
                            "hash": page_hash
                        })
                
                all_results[topic] = {"pages": processed_pages}
            
            return all_results
    
    def save_topics_to_file(self, topics, query):
        """
        Сохраняет список тем в файл
        
        Args:
            topics (list): Список тем для поиска
            query (str): Исходный запрос пользователя
            
        Returns:
            str: Путь к сохраненному файлу
        """
        try:
            # Создаем файл с темами
            sanitized_query = "".join(c if c.isalnum() else "_" for c in query)
            output_file = f"topics_{sanitized_query}.md"
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Темы для поиска по запросу: {query}\n\n")
                
                for i, topic in enumerate(topics, 1):
                    f.write(f"{i}. {topic}\n")
            
            print(f"Список тем сохранен в файл: {output_file}")
            return output_file
        except Exception as e:
            print(f"Произошла ошибка при сохранении списка тем: {e}")
            return None
    
    def save_results_to_json(self, results, query):
        """
        Сохраняет результаты поиска в файл JSON
        
        Args:
            results (dict): Результаты поиска
            query (str): Исходный запрос пользователя
            
        Returns:
            str: Путь к сохраненному файлу
        """
        try:
            # Подготавливаем структуру для сохранения в JSON
            json_results = {
                "query": query,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "topics": {}
            }
            
            for topic, data in results.items():
                json_results["topics"][topic] = {
                    "pages": []
                }
                
                for page in data["pages"]:
                    json_results["topics"][topic]["pages"].append({
                        "title": page["title"],
                        "url": page["url"],
                        "content_file": page["content_file"],
                        "hash": page["hash"]
                    })
            
            # Сохраняем результаты в JSON файл
            sanitized_query = "".join(c if c.isalnum() else "_" for c in query)
            output_file = f"results_{sanitized_query}.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(json_results, f, ensure_ascii=False, indent=2)
            
            print(f"Результаты сохранены в файл: {output_file}")
            return output_file
        except Exception as e:
            print(f"Произошла ошибка при сохранении результатов: {e}")
            return None
    
    def save_results_to_markdown(self, results, query, output_file="search_results.md"):
        """
        Сохраняет результаты поиска в файл Markdown (для обратной совместимости)
        
        Args:
            results (dict): Результаты поиска
            query (str): Исходный запрос пользователя
            output_file (str): Имя выходного файла
            
        Returns:
            str: Путь к сохраненному файлу
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Результаты поиска по запросу: {query}\n\n")
                
                for topic, data in results.items():
                    f.write(f"## Тема: {topic}\n\n")
                    
                    if not data["pages"]:
                        f.write("*Результаты не найдены*\n\n")
                        continue
                    
                    for page in data["pages"]:
                        f.write(f"### {page['title']}\n\n")
                        f.write(f"URL: {page['url']}\n\n")
                        
                        # Читаем содержимое из кэш-файла
                        try:
                            with open(page["content_file"], "r", encoding="utf-8") as cache_file:
                                # Пропускаем первые 3 строки (заголовок и URL)
                                lines = cache_file.readlines()[3:]
                                f.write("".join(lines) + "\n\n")
                        except Exception as e:
                            f.write(f"*Ошибка при чтении содержимого: {e}*\n\n")
                        
                        f.write("---\n\n")
            
            print(f"Результаты также сохранены в файл: {output_file}")
            return output_file
        except Exception as e:
            print(f"Произошла ошибка при сохранении результатов в Markdown: {e}")
            return None

# Функция для выполнения поиска по списку тем
def run_search(topics, query, output_file="search_results.md"):
    """
    Выполняет поиск по списку тем и сохраняет результаты
    
    Args:
        topics (list): Список тем для поиска
        query (str): Исходный запрос пользователя
        output_file (str): Имя выходного файла для Markdown (для обратной совместимости)
        
    Returns:
        tuple: Пути к сохраненным файлам (topics_file, results_json, results_md)
    """
    search_engine = SearchEngine()
    
    # Сохраняем список тем
    topics_file = search_engine.save_topics_to_file(topics, query)
    
    # Запускаем асинхронный поиск
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(search_engine.process_search_results(topics))
    
    # Сохраняем результаты в JSON
    results_json = search_engine.save_results_to_json(results, query)
    
    # Для обратной совместимости сохраняем результаты в Markdown
    results_md = search_engine.save_results_to_markdown(results, query, output_file)
    
    return (topics_file, results_json, results_md)


if __name__ == "__main__":
    # Пример использования
    test_topics = [
        "Принципы работы квантового компьютера",
        "Кубиты и квантовая запутанность"
    ]
    
    topic_file, json_file, md_file = run_search(test_topics, "Как работает квантовый компьютер")
    print(f"Сохранено: темы - {topic_file}, результаты JSON - {json_file}, результаты MD - {md_file}")
