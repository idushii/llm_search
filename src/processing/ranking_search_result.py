"""
Модуль для ранжирования результатов поиска
"""
import json
import os
from collections import Counter

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
        Ранжирует результаты поиска по релевантности к исходному запросу
        
        Args:
            search_results (dict): Словарь с результатами поиска
            original_query (str): Исходный запрос пользователя
            
        Returns:
            list: Список отсортированных результатов с рейтингом
        """
        # Разбиваем запрос на ключевые слова для анализа
        query_words = set(original_query.lower().split())
        
        all_results = []
        
        # Обрабатываем результаты для каждого подзапроса
        for subtopic, results in search_results.items():
            for result in results:
                # Расчет рейтинга на основе текста сниппета и заголовка
                title = result.get("title", "").lower()
                snippet = result.get("snippet", "").lower()
                
                # Считаем вхождения ключевых слов из запроса
                title_score = sum(1 for word in query_words if word in title)
                snippet_score = sum(1 for word in query_words if word in snippet)
                
                # Базовый рейтинг - сумма вхождений в заголовок и сниппет с разными весами
                base_score = (title_score * 2) + snippet_score
                
                # Дополнительные факторы ранжирования
                additional_score = 0
                
                # Бонус за точное соответствие запросу в заголовке
                if original_query.lower() in title:
                    additional_score += 5
                
                # Бонус за точное соответствие запросу в сниппете
                if original_query.lower() in snippet:
                    additional_score += 3
                
                # Общий рейтинг
                total_score = base_score + additional_score
                
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