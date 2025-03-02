import os
import requests
import json
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# API-ключ для доступа к LLM
API_KEY = os.getenv("AITUNNEL_API_KEY")

# URL для API LLM
API_URL = "https://api.aitunnel.ru/v1/chat/completions"

COUNT_RU_TOPICS = os.getenv("COUNT_RU_TOPICS")
COUNT_EN_TOPICS = os.getenv("COUNT_EN_TOPICS")

class QueryPlanner:
    """
    Класс для планирования поисковых запросов с использованием LLM
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or API_KEY
        if not self.api_key:
            raise ValueError("API ключ не найден. Установите переменную окружения AITUNNEL_API_KEY или передайте ключ при создании экземпляра.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_search_topics(self, query):
        """
        Генерирует список тем для поиска на основе исходного запроса
        
        Args:
            query (str): Исходный запрос пользователя
            
        Returns:
            list: Список тем для поиска
        """
        try:
            payload = {
                "model": os.getenv("AITUNNEL_MODEL"),
                "max_tokens": 50000,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Составь список из {COUNT_RU_TOPICS} тем для поиска в интернете по запросу: {query} на русском языке и {COUNT_EN_TOPICS} на английском языке. "
                                   f"Каждая тема должна быть на отдельной строке с префиксом 'ТЕМА:' и должна быть короткой и чёткой. "
                                   f"Темы должны покрывать разные аспекты запроса. "
                                   f"Темы должны быть на русском языке или на английском языке."
                    }
                ]
            }
            
            response = requests.post(API_URL, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Извлекаем темы из ответа
                topics = []
                for line in content.split("\n"):
                    if line.strip().startswith("ТЕМА:"):
                        topic = line.replace("ТЕМА:", "").strip()
                        if topic:
                            topics.append(topic)
                
                return topics
            else:
                print(f"Ошибка при обращении к API: {response.status_code}")
                print(response.text)
                return []
                
        except Exception as e:
            print(f"Произошла ошибка при генерации тем: {e}")
            return []


if __name__ == "__main__":
    # Пример использования
    planner = QueryPlanner()
    topics = planner.generate_search_topics("Как работает квантовый компьютер")
    print("Сгенерированные темы для поиска:")
    for i, topic in enumerate(topics, 1):
        print(f"{i}. {topic}")
