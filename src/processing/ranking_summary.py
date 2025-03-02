"""
Модуль для ранжирования саммари
"""
import os
import json
import re
from collections import Counter

from src.core.utils import logger
from src.core.config import RANKING_SUMMARY_PROMPT

class SummaryRanker:
    """
    Класс для ранжирования саммари документов
    """
    def __init__(self):
        pass
    
    def extract_keywords(self, text):
        """
        Извлекает ключевые слова из текста
        
        Args:
            text (str): Исходный текст
            
        Returns:
            list: Список ключевых слов
        """
        # Удаляем специальные символы и приводим к нижнему регистру
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Разбиваем на слова
        words = text.split()
        
        # Фильтруем стоп-слова (можно расширить список)
        stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'от', 'к', 'за', 'из', 'под', 'над', 'о', 'об', 'при', 
                     'что', 'как', 'когда', 'где', 'который', 'это', 'этот', 'эта', 'эти', 'тот', 'та', 'те',
                     'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as', 'into',
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did'}
        
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        return filtered_words
    
    def rank_by_keywords(self, summaries, original_query):
        """
        Ранжирует саммари по релевантности к исходному запросу с использованием LLM
        
        Args:
            summaries (list): Список саммари
            original_query (str): Исходный запрос пользователя
            
        Returns:
            list: Список отсортированных саммари с рейтингом
        """
        import requests
        import time
        from src.core.config import AITUNNEL_API_KEY, AITUNNEL_MODEL, AITUNNEL_API_URL, AITUNNEL_RPS
        
        ranked_summaries = []
        
       
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AITUNNEL_API_KEY}"
        }
        
        logger.info(f"Ранжирование саммари для запроса: {original_query}")
        
        for summary_doc in summaries:
            summary_text = summary_doc.get("summary", "")
            title = summary_doc.get("title", "")
            url = summary_doc.get("url", "")
            
            # Если саммари нет, пропускаем документ
            if not summary_text:
                continue
            
            # Ограничиваем длину саммари для запроса (примерно 1 токен = 4 символа)
            truncated_summary = summary_text[:4000]
            
            # Формируем запрос для LLM
            user_message = f"""
            Исходный запрос пользователя: {original_query}
            
            Саммари документа:
            Заголовок: {title}
            URL: {url}
            
            Текст саммари:
            {truncated_summary}
            """
            
            payload = {
                "model": AITUNNEL_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": RANKING_SUMMARY_PROMPT
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
                            
                            # Копируем документ с саммари и добавляем поле с рейтингом и оценками
                            ranked_summary = summary_doc.copy()
                            ranked_summary["rank"] = total_score
                            ranked_summary["ratings"] = ratings
                            
                            ranked_summaries.append(ranked_summary)
                            
                            logger.info(f"Рейтинг для саммари '{title}': {total_score}")
                        else:
                            logger.error(f"Не удалось извлечь JSON из ответа LLM: {llm_text}")
                            
                            # Если не удалось получить JSON, используем базовый рейтинг
                            ranked_summary = summary_doc.copy()
                            ranked_summary["rank"] = 5.0  # Средний рейтинг по умолчанию
                            
                            ranked_summaries.append(ranked_summary)
                    except json.JSONDecodeError as json_error:
                        logger.error(f"Ошибка при разборе JSON из ответа LLM: {json_error}")
                        
                        # Если не удалось разобрать JSON, используем базовый рейтинг
                        ranked_summary = summary_doc.copy()
                        ranked_summary["rank"] = 5.0  # Средний рейтинг по умолчанию
                        
                        ranked_summaries.append(ranked_summary)
                else:
                    logger.error(f"Ошибка при запросе к LLM API: {response.status_code}, {response.text}")
                    
                    # Если запрос не удался, используем базовый рейтинг
                    ranked_summary = summary_doc.copy()
                    ranked_summary["rank"] = 5.0  # Средний рейтинг по умолчанию
                    
                    ranked_summaries.append(ranked_summary)
                
            except Exception as e:
                logger.error(f"Ошибка при ранжировании саммари с помощью LLM: {e}")
                
                # Если возникла ошибка, используем базовый алгоритм ранжирования на основе ключевых слов
                # Извлекаем ключевые слова из запроса
                query_keywords = self.extract_keywords(original_query)
                
                # Извлекаем ключевые слова из саммари
                summary_keywords = self.extract_keywords(summary_text)
                
                # Подсчитываем вхождения ключевых слов из запроса в саммари
                keyword_count = sum(1 for word in summary_keywords if word in query_keywords)
                
                # Нормализуем на длину текста для предотвращения перекоса в сторону длинных текстов
                normalized_score = keyword_count / (len(summary_keywords) + 1) * 100
                
                # Добавляем бонус за точные фразы из запроса
                exact_phrase_bonus = 0
                for i in range(len(query_keywords) - 1):
                    phrase = f"{query_keywords[i]} {query_keywords[i+1]}"
                    if phrase in " ".join(summary_keywords):
                        exact_phrase_bonus += 5
                
                # Итоговый рейтинг, нормализуем до шкалы 0-10
                total_score = min(10, (normalized_score + exact_phrase_bonus) / 20)
                
                # Создаем копию документа с рейтингом
                ranked_summary = summary_doc.copy()
                ranked_summary["rank"] = total_score
                
                ranked_summaries.append(ranked_summary)
        
        # Сортируем саммари по рейтингу (от большего к меньшему)
        sorted_summaries = sorted(ranked_summaries, key=lambda x: x["rank"], reverse=True)
        
        return sorted_summaries
    
    def select_top_summaries(self, ranked_summaries, top_n=5):
        """
        Выбирает top_n наиболее релевантных саммари
        
        Args:
            ranked_summaries (list): Список отсортированных саммари с рейтингом
            top_n (int): Количество саммари для выбора
            
        Returns:
            list: Список top_n наиболее релевантных саммари
        """
        return ranked_summaries[:top_n]
    
    def process_summaries(self, documents_with_summaries, original_query, top_n=5):
        """
        Обрабатывает саммари: ранжирует и выбирает топ
        
        Args:
            documents_with_summaries (list): Список документов с саммари
            original_query (str): Исходный запрос пользователя
            top_n (int): Количество саммари для выбора
            
        Returns:
            list: Список top_n наиболее релевантных саммари
        """
        # Фильтруем документы без саммари
        valid_summaries = [doc for doc in documents_with_summaries if "summary" in doc and doc["summary"]]
        
        # Ранжируем саммари
        ranked_summaries = self.rank_by_keywords(valid_summaries, original_query)
        
        # Выбираем топ N саммари
        top_summaries = self.select_top_summaries(ranked_summaries, top_n)
        
        return top_summaries
    
    def save_ranked_summaries_to_json(self, ranked_summaries, theme_name, cache_dir="cache"):
        """
        Сохраняет отранжированные саммари в JSON файл
        
        Args:
            ranked_summaries (list): Список отранжированных саммари
            theme_name (str): Название темы (для имени файла)
            cache_dir (str): Директория кэша
            
        Returns:
            str: Путь к созданному файлу или None в случае ошибки
        """
        try:
            # Создаем директорию для отранжированных саммари
            ranked_summaries_dir = os.path.join(cache_dir, "ranked_summaries")
            os.makedirs(ranked_summaries_dir, exist_ok=True)
            
            # Генерируем имя файла
            file_path = os.path.join(ranked_summaries_dir, f"{theme_name}.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(ranked_summaries, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Отранжированные саммари сохранены в файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при сохранении отранжированных саммари: {e}")
            return None 