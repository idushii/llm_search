"""
Утилиты проекта
"""
import os
import sys
import time
import logging
import hashlib
import re
from datetime import datetime

from src.core.constants import TIMESTAMP_FORMAT

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mind_search.log")
    ]
)

logger = logging.getLogger("mind-search")

def generate_hash(text):
    """
    Генерирует MD5 хеш от текста для использования в именах файлов
    
    Args:
        text (str): Исходный текст
        
    Returns:
        str: Хеш в виде шестнадцатеричной строки
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def sanitize_filename(text, max_length=30):
    """
    Преобразует текст в безопасное имя файла
    
    Args:
        text (str): Исходный текст
        max_length (int): Максимальная длина имени
        
    Returns:
        str: Безопасное имя файла
    """
    # Заменяем небезопасные символы на подчеркивание
    sanitized = re.sub(r'[^\w\s-]', '_', text)
    # Заменяем пробелы на подчеркивание
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Обрезаем до максимальной длины
    return sanitized[:max_length]

def generate_timestamp():
    """
    Генерирует текущую временную метку
    
    Returns:
        str: Временная метка в формате YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime(TIMESTAMP_FORMAT)

def create_directory(directory_path):
    """
    Создает директорию, если она не существует
    
    Args:
        directory_path (str): Путь к директории
        
    Returns:
        bool: True, если директория создана или уже существует
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании директории {directory_path}: {e}")
        return False

def print_progress(current, total, prefix='Прогресс:', suffix='Завершено', length=50):
    """
    Выводит прогресс-бар в консоль
    
    Args:
        current (int): Текущий шаг
        total (int): Всего шагов
        prefix (str): Текст перед прогресс-баром
        suffix (str): Текст после прогресс-бара
        length (int): Длина прогресс-бара в символах
    """
    percent = int(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if current == total:
        print()

def show_animation(animation_chars=["|", "/", "-", "\\"], duration=0.5, cycles=3):
    """
    Показывает анимацию в консоли
    
    Args:
        animation_chars (list): Символы для анимации
        duration (float): Продолжительность одного шага
        cycles (int): Количество циклов
    """
    for _ in range(cycles):
        for char in animation_chars:
            sys.stdout.write(f"\r{char}")
            sys.stdout.flush()
            time.sleep(duration)
    sys.stdout.write('\r')
    sys.stdout.flush()

def extract_text_between_prefix(text, prefix):
    """
    Извлекает текст после префикса до конца строки
    
    Args:
        text (str): Исходный текст
        prefix (str): Префикс для поиска
        
    Returns:
        list: Список строк, содержащих текст после префикса
    """
    result = []
    for line in text.split('\n'):
        if line.strip().startswith(prefix):
            content = line.replace(prefix, "").strip()
            if content:
                result.append(content)
    return result

def count_words(text):
    """
    Подсчитывает количество слов в тексте
    
    Args:
        text (str): Исходный текст
        
    Returns:
        int: Количество слов
    """
    words = re.findall(r'\b\w+\b', text)
    return len(words) 