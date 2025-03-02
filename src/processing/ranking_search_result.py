"""
Модуль для ранжирования результатов поиска
"""
import json
import os
from collections import Counter

from src.core.config import RANKING_SEARCH_RESULT_PROMPT
from src.core.utils import logger

class SearchResultRanker:
    """
    Класс для ранжирования результатов поиска
    """
    def __init__(self):
        pass
    
    def filter_duplicates(self, search_results):
        """
        Фильтрует дубликаты результатов поиска по URL
        
        Args:
            search_results (dict): Словарь с результатами поиска
            
        Returns:
            dict: Отфильтрованный словарь с результатами
        """
        filtered_results = {}
        seen_urls = set()
        
        for subtopic, results in search_results.items():
            filtered_subtopic_results = []
            
            for result in results:
                url = result.get("url")
                
                # Если URL уже был обработан, пропускаем результат
                if url in seen_urls:
                    continue
                    
                seen_urls.add(url)
                filtered_subtopic_results.append(result)
            
            filtered_results[subtopic] = filtered_subtopic_results
        
        return filtered_results
    
    def rank_by_relevance(self, search_results, original_query):
        """
        Ранжирует результаты поиска по релевантности к исходному запросу, используя LLM
        
        Args:
            search_results (dict): Словарь с результатами поиска
            original_query (str): Исходный запрос пользователя
            
        Returns:
            list: Список отсортированных результатов с рейтингом
        """
        import requests
        import time
        from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS
        
        all_results = []
                
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AITUNNEL_API_KEY}"
        }
        
        # Обрабатываем результаты для каждого подзапроса
        for subtopic, results in search_results.items():
            logger.info(f"Ранжирование результатов для подзапроса: {subtopic}")
            
            for result in results:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                url = result.get("url", "")
                
                # Формируем запрос для LLM
                user_message = f"""
                Исходный запрос пользователя: {original_query}
                Подзапрос: {subtopic}
                
                Результат поиска:
                Заголовок: {title}
                Сниппет: {snippet}
                URL: {url}
                """
                
                payload = {
                    "model": AITUNNEL_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": RANKING_SEARCH_RESULT_PROMPT
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                }
                
                # Ограничиваем частоту запросов к API
                time.sleep(1.0 / AITUNNEL_RPS)
                
                try:
                    response = requests.post(AITUNNEL_API_URL, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        llm_response = response.json()
                        llm_text = llm_response["choices"][0]["message"]["content"]
                        
                        try:
                            # Извлекаем JSON из ответа
                            import json
                            import re
                            
                            # Ищем JSON в ответе с помощью регулярного выражения
                            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_text, re.DOTALL)
                            
                            if json_match:
                                ratings_json = json_match.group(1)
                                ratings = json.loads(ratings_json)
                                
                                # Получаем итоговый рейтинг
                                total_score = ratings.get("итоговый_рейтинг", 0)
                                
                                # Копируем результат и добавляем поле с рейтингом и оценками
                                ranked_result = result.copy()
                                ranked_result["rank"] = total_score
                                ranked_result["ratings"] = ratings
                                ranked_result["subtopic"] = subtopic
                                
                                all_results.append(ranked_result)
                                
                                logger.info(f"Рейтинг для {title}: {total_score}")
                            else:
                                logger.error(f"Не удалось извлечь JSON из ответа LLM: {llm_text}")
                                
                                # Если не удалось получить JSON, используем базовый рейтинг
                                ranked_result = result.copy()
                                ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                                ranked_result["subtopic"] = subtopic
                                
                                all_results.append(ranked_result)
                        except json.JSONDecodeError as json_error:
                            logger.error(f"Ошибка при разборе JSON из ответа LLM: {json_error}")
                            
                            # Если не удалось разобрать JSON, используем базовый рейтинг
                            ranked_result = result.copy()
                            ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                            ranked_result["subtopic"] = subtopic
                            
                            all_results.append(ranked_result)
                    else:
                        logger.error(f"Ошибка при запросе к LLM API: {response.status_code}, {response.text}")
                        
                        # Если запрос не удался, используем базовый рейтинг
                        ranked_result = result.copy()
                        ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                        ranked_result["subtopic"] = subtopic
                        
                        all_results.append(ranked_result)
                        
                except Exception as e:
                    logger.error(f"Ошибка при ранжировании с помощью LLM: {e}")
                    
                    # Если возникла ошибка, используем базовый алгоритм ранжирования
                    # Расчет рейтинга на основе текста сниппета и заголовка
                    query_words = set(original_query.lower().split())
                    title_lower = title.lower()
                    snippet_lower = snippet.lower()
                    
                    # Считаем вхождения ключевых слов из запроса
                    title_score = sum(1 for word in query_words if word in title_lower)
                    snippet_score = sum(1 for word in query_words if word in snippet_lower)
                    
                    # Базовый рейтинг - сумма вхождений в заголовок и сниппет с разными весами
                    base_score = (title_score * 2) + snippet_score
                    
                    # Дополнительные факторы ранжирования
                    additional_score = 0
                    
                    # Бонус за точное соответствие запросу в заголовке
                    if original_query.lower() in title_lower:
                        additional_score += 5
                    
                    # Бонус за точное соответствие запросу в сниппете
                    if original_query.lower() in snippet_lower:
                        additional_score += 3
                    
                    # Общий рейтинг, нормализуем до шкалы 0-10
                    total_score = min(10, (base_score + additional_score) / 2)
                    
                    # Копируем результат и добавляем поле с рейтингом
                    ranked_result = result.copy()
                    ranked_result["rank"] = total_score
                    ranked_result["subtopic"] = subtopic
                    
                    all_results.append(ranked_result)
        
        # Сортируем результаты по рейтингу (от большего к меньшему)
        sorted_results = sorted(all_results, key=lambda x: x["rank"], reverse=True)
        
        return sorted_results
    
    def select_top_results(self, ranked_results, top_n=5):
        """
        Выбирает top_n наиболее релевантных результатов
        
        Args:
            ranked_results (list): Список отсортированных результатов с рейтингом
            top_n (int): Количество результатов для выбора
            
        Returns:
            list: Список top_n наиболее релевантных результатов
        """
        return ranked_results[:top_n]
    
    def process_search_results(self, search_results, original_query, top_n=5):
        """
        Обрабатывает результаты поиска: фильтрует дубликаты, ранжирует и выбирает топ
        
        Args:
            search_results (dict): Словарь с результатами поиска
            original_query (str): Исходный запрос пользователя
            top_n (int): Количество результатов для выбора
            
        Returns:
            list: Список top_n наиболее релевантных результатов
        """
        # Фильтруем дубликаты
        filtered_results = self.filter_duplicates(search_results)
        
        # Ранжируем результаты
        ranked_results = self.rank_by_relevance(filtered_results, original_query)
        
        # Выбираем топ N результатов
        top_results = self.select_top_results(ranked_results, top_n)
        
        return top_results
    
    def save_ranked_results_to_json(self, ranked_results, theme_name, cache_dir="cache"):
        """
        Сохраняет отранжированные результаты в JSON файл
        
        Args:
            ranked_results (list): Список отранжированных результатов
            theme_name (str): Название темы (для имени файла)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для результатов ранжирования
            ranked_results_dir = os.path.join(cache_dir, "ranked_results")
            os.makedirs(ranked_results_dir, exist_ok=True)
            
            # Генерируем имя файла
            file_path = os.path.join(ranked_results_dir, f"{theme_name}.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(ranked_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Отранжированные результаты сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении отранжированных результатов: {e}")
            return None 