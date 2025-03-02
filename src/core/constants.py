"""
Константы проекта
"""

# Префиксы для запросов
SUBTOPIC_PREFIX = "ПОДЗАПРОС:"
QUERY_PREFIX = "ЗАПРОС:"

# Названия файлов
REQUEST_FILE = "request.md"
ANSWER_FILE = "answer.md"

# Настройки кэширования
CACHE_VERSION = "1.0"

# Настройки для запросов
DEFAULT_TIMEOUT = 30  # секунды
MAX_RETRIES = 3

# HTTP коды
HTTP_OK = 200
HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNAUTHORIZED = 401

# Форматы временных меток
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# Максимальное количество токенов для запросов
MAX_TOKENS = 8192 