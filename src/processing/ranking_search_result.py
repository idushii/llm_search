"""
Модуль для ранжирования результатов поиска
"""
import json
import os
from collections import Counter

from src.core.config import RANKING_SEARCH_RESULT_PROMPT, RANKING_SEARCH_RESULT_BATCH_PROMPT
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
        total_results = sum(len(results) for results in search_results.values())
        processed_results = 0
                
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AITUNNEL_API_KEY}"
        }
        
        print(f"\nНачинаю ранжирование {total_results} результатов поиска с использованием LLM...")
        print("Оценка будет проводиться по 5 критериям от 0 до 10:")
        print("1. Соответствие исходному запросу")
        print("2. Соответствие направлению поиска (подзапросу)")
        print("3. Полнота информации")
        print("4. Точность данных")
        print("5. Читабельность и структура")
        
        # Обрабатываем результаты для каждого подзапроса
        for subtopic, results in search_results.items():
            logger.info(f"Ранжирование результатов для подзапроса: {subtopic}")
            print(f"\nРанжирование результатов для подзапроса: {subtopic}")
            
            for result in results:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                url = result.get("url", "")
                
                processed_results += 1
                progress = (processed_results / total_results) * 100
                print(f"[{processed_results}/{total_results}] ({progress:.1f}%) Оценка: {title[:50]}...", end="\r")
                
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
        
        print("\n\nРанжирование результатов завершено.")
        print(f"Из {total_results} результатов поиска были оценены все.")
        
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
        # Выводим информацию о выбранных результатах
        print(f"\nВыбраны топ-{top_n} наиболее релевантных результатов для дальнейшей обработки:")
        
        top_results = ranked_results[:top_n]
        
        for i, result in enumerate(top_results, 1):
            title = result.get("title", "")
            rank = result.get("rank", 0)
            subtopic = result.get("subtopic", "")
            
            print(f"{i}. [{rank:.1f}] {title} (подзапрос: {subtopic})")
        
        return top_results
    
    def rank_by_relevance_batch(self, search_results, original_query):
        """
        Ранжирует результаты поиска группами по 10 результатов, используя пагинацию.
        Это значительно ускоряет процесс ранжирования и сокращает количество API запросов.
        
        Args:
            search_results (dict): Словарь с результатами поиска
            original_query (str): Исходный запрос пользователя
            
        Returns:
            list: Список отсортированных результатов с рейтингом
        """
        import requests
        import time
        import math
        from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS
        
        all_results = []
        batch_size = 10  # Размер пакета для одновременной оценки
        total_results = sum(len(results) for results in search_results.values())
        processed_results = 0
        
        # Формируем плоский список всех результатов поиска
        flat_results = []
        for subtopic, results in search_results.items():
            for result in results:
                result_copy = result.copy()
                result_copy["subtopic"] = subtopic
                flat_results.append(result_copy)
        
        # Рассчитываем количество пакетов
        total_batches = math.ceil(len(flat_results) / batch_size)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AITUNNEL_API_KEY}"
        }
        
        print(f"\nНачинаю ранжирование {total_results} результатов поиска с использованием LLM (пакетами по {batch_size})...")
        print(f"Всего будет обработано {total_batches} пакетов результатов.")
        print("Оценка будет проводиться по 5 критериям от 0 до 10:")
        print("1. Соответствие исходному запросу")
        print("2. Соответствие направлению поиска (подзапросу)")
        print("3. Полнота информации")
        print("4. Точность данных")
        print("5. Читабельность и структура")
        
        # Обрабатываем результаты пакетами
        for batch_index in range(total_batches):
            batch_start = batch_index * batch_size
            batch_end = min(batch_start + batch_size, len(flat_results))
            current_batch = flat_results[batch_start:batch_end]
            
            print(f"\nОбработка пакета {batch_index + 1}/{total_batches} ({batch_end - batch_start} результатов)")
            
            # Формируем запрос для LLM
            batch_content = ""
            for i, result in enumerate(current_batch, 1):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                url = result.get("url", "")
                subtopic = result.get("subtopic", "")
                
                batch_content += f"""
                ### Результат #{i}:
                Подзапрос: {subtopic}
                Заголовок: {title}
                Сниппет: {snippet}
                URL: {url}
                
                """
            
            user_message = f"""
            Исходный запрос пользователя: {original_query}
            
            Оцени следующие результаты поиска по указанным критериям:
            
            {batch_content}
            """
            
            payload = {
                "model": AITUNNEL_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": RANKING_SEARCH_RESULT_BATCH_PROMPT
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
                response = requests.post(AITUNNEL_API_URL, json=payload, headers=headers)
                
                if response.status_code == 200:
                    response_data = response.json()
                    llm_text = response_data["choices"][0]["message"]["content"]
                    
                    # Извлекаем JSON из ответа LLM
                    import re
                    json_pattern = r'```json\s*([\s\S]*?)\s*```'
                    json_match = re.search(json_pattern, llm_text)
                    
                    if json_match:
                        ratings_json = json_match.group(1)
                        try:
                            ratings_array = json.loads(ratings_json)
                            
                            if isinstance(ratings_array, list):
                                # Обрабатываем каждый результат из массива оценок
                                for rating_item in ratings_array:
                                    result_title = rating_item.get("заголовок", "")
                                    
                                    # Ищем результат по заголовку
                                    matching_results = [r for r in current_batch if r.get("title", "") == result_title]
                                    
                                    if matching_results:
                                        original_result = matching_results[0]
                                        
                                        # Копируем результат и добавляем рейтинг
                                        ranked_result = original_result.copy()
                                        ranked_result["rank"] = rating_item.get("итоговый_рейтинг", 5.0)
                                        ranked_result["ratings"] = {
                                            "соответствие_запросу": rating_item.get("соответствие_запросу", 5.0),
                                            "соответствие_направлению": rating_item.get("соответствие_направлению", 5.0),
                                            "полнота": rating_item.get("полнота", 5.0),
                                            "точность": rating_item.get("точность", 5.0),
                                            "структура": rating_item.get("структура", 5.0),
                                            "итоговый_рейтинг": rating_item.get("итоговый_рейтинг", 5.0)
                                        }
                                        
                                        all_results.append(ranked_result)
                                        
                                        logger.info(f"Рейтинг для {result_title}: {ranked_result['rank']}")
                                    else:
                                        logger.error(f"Ошибка: не найден результат с заголовком {result_title}")
                                
                                # Проверяем, все ли результаты из пакета были оценены
                                processed_titles = [r.get("заголовок", "") for r in ratings_array]
                                for result in current_batch:
                                    title = result.get("title", "")
                                    if title not in processed_titles:
                                        logger.warning(f"Результат с заголовком '{title}' не был оценен, использую значение по умолчанию")
                                        
                                        # Для неоцененных результатов используем средний рейтинг
                                        ranked_result = result.copy()
                                        ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                                        all_results.append(ranked_result)
                            else:
                                logger.error(f"Ошибка: ответ LLM не содержит массив оценок")
                                
                                # Применяем базовое ранжирование к текущему пакету
                                for result in current_batch:
                                    ranked_result = result.copy()
                                    ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                                    all_results.append(ranked_result)
                        except json.JSONDecodeError as json_error:
                            logger.error(f"Ошибка при разборе JSON из ответа LLM: {json_error}")
                            
                            # Применяем базовое ранжирование к текущему пакету
                            for result in current_batch:
                                ranked_result = result.copy()
                                ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                                all_results.append(ranked_result)
                    else:
                        logger.error(f"Не удалось извлечь JSON из ответа LLM: {llm_text}")
                        
                        # Применяем базовое ранжирование к текущему пакету
                        for result in current_batch:
                            ranked_result = result.copy()
                            ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                            all_results.append(ranked_result)
                else:
                    logger.error(f"Ошибка при запросе к LLM API: {response.status_code}, {response.text}")
                    
                    # Применяем базовое ранжирование к текущему пакету
                    for result in current_batch:
                        ranked_result = result.copy()
                        ranked_result["rank"] = 5.0  # Средний рейтинг по умолчанию
                        all_results.append(ranked_result)
            except Exception as e:
                logger.error(f"Ошибка при ранжировании пакета с помощью LLM: {e}")
                
                # Применяем базовое ранжирование к текущему пакету в случае ошибки
                for result in current_batch:
                    # Базовое ранжирование на основе ключевых слов
                    query_words = set(original_query.lower().split())
                    title_lower = result.get("title", "").lower()
                    snippet_lower = result.get("snippet", "").lower()
                    
                    # Считаем вхождения ключевых слов из запроса
                    title_score = sum(1 for word in query_words if word in title_lower)
                    snippet_score = sum(1 for word in query_words if word in snippet_lower)
                    
                    # Базовый рейтинг
                    base_score = (title_score * 2) + snippet_score
                    
                    # Дополнительные факторы ранжирования
                    additional_score = 0
                    if original_query.lower() in title_lower:
                        additional_score += 5
                    if original_query.lower() in snippet_lower:
                        additional_score += 3
                    
                    # Общий рейтинг, нормализуем до шкалы 0-10
                    total_score = min(10, (base_score + additional_score) / 2)
                    
                    # Копируем результат и добавляем поле с рейтингом
                    ranked_result = result.copy()
                    ranked_result["rank"] = total_score
                    
                    all_results.append(ranked_result)
            
            # Обновляем счетчик обработанных результатов
            processed_results += len(current_batch)
            progress = (processed_results / total_results) * 100
            print(f"Обработано {processed_results}/{total_results} результатов ({progress:.1f}%)")
        
        # Сортируем результаты по рейтингу (от большего к меньшему)
        sorted_results = sorted(all_results, key=lambda x: x["rank"], reverse=True)
        
        print("\n\nРанжирование результатов завершено.")
        print(f"Из {total_results} результатов поиска были оценены все.")
        
        return sorted_results
    
    def process_search_results(self, search_results, original_query, top_n=25):
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
        
        # Определяем, какой метод ранжирования использовать
        total_results = sum(len(results) for results in filtered_results.values())
        if total_results > 10:
            # Используем пакетное ранжирование для большого количества результатов
            print(f"Обнаружено {total_results} результатов, использую пакетное ранжирование")
            ranked_results = self.rank_by_relevance_batch(filtered_results, original_query)
        else:
            # Используем обычное ранжирование для небольшого количества результатов
            print(f"Обнаружено {total_results} результатов, использую стандартное ранжирование")
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
            # Создаем директорию для результатов поиска
            ranked_results_dir = os.path.join(cache_dir, theme_name)
            os.makedirs(ranked_results_dir, exist_ok=True)
            
            # Формируем имя файла
            file_path = os.path.join(ranked_results_dir, f"ranked_results.json")
            
            # Сохраняем данные в JSON формате с красивым форматированием
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(ranked_results, file, ensure_ascii=False, indent=4)
            
            logger.info(f"Отранжированные результаты сохранены в {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении отранжированных результатов: {e}")
            return None 