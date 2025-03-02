"""
Модуль для управления кэшированием данных
"""
import os
import json
import shutil
from datetime import datetime, timedelta

from src.core.utils import logger, generate_hash, sanitize_filename, create_directory
from src.core.config import CACHE_DIR, DOCS_DIR, SUMMARIES_DIR
from src.core.constants import CACHE_VERSION

class CacheManager:
    """
    Класс для управления кэшированием данных поиска и обработки
    """
    def __init__(self, cache_dir=None, max_age_days=30):
        """
        Инициализирует менеджер кэша
        
        Args:
            cache_dir (str, optional): Путь к директории кэша. По умолчанию используется CACHE_DIR из config.py
            max_age_days (int, optional): Максимальный возраст кэша в днях. По умолчанию 30 дней.
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.max_age_days = max_age_days
        
        # Создаем базовые директории для кэша
        create_directory(self.cache_dir)
        create_directory(DOCS_DIR)
        create_directory(SUMMARIES_DIR)
    
    def generate_theme_name(self, query):
        """
        Генерирует имя темы для хранения кэша на основе запроса
        
        Args:
            query (str): Исходный запрос пользователя
            
        Returns:
            str: Имя темы
        """
        # Генерируем безопасное имя файла из запроса
        sanitized_query = sanitize_filename(query, max_length=50)
        
        # Добавляем хеш для уникальности
        query_hash = generate_hash(query)[:8]
        
        # Формируем итоговое имя темы
        theme_name = f"{sanitized_query}_{query_hash}"
        
        return theme_name
    
    def clear_expired_cache(self):
        """
        Очищает устаревший кэш, старше max_age_days
        
        Returns:
            int: Количество удаленных файлов/директорий
        """
        total_removed = 0
        now = datetime.now()
        max_age = timedelta(days=self.max_age_days)
        
        try:
            # Проверяем все файлы в директории кэша
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_stat = os.stat(file_path)
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # Если файл старше максимального возраста, удаляем его
                    if now - file_time > max_age:
                        try:
                            os.remove(file_path)
                            total_removed += 1
                            logger.debug(f"Удален устаревший файл кэша: {file_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при удалении файла {file_path}: {e}")
                
                # Удаляем пустые директории
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if not os.listdir(dir_path):
                        try:
                            os.rmdir(dir_path)
                            logger.debug(f"Удалена пустая директория: {dir_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при удалении директории {dir_path}: {e}")
            
            logger.info(f"Очистка кэша завершена. Удалено {total_removed} устаревших файлов.")
            return total_removed
            
        except Exception as e:
            logger.error(f"Ошибка при очистке кэша: {e}")
            return 0
    
    def get_cache_info(self):
        """
        Возвращает информацию о кэше
        
        Returns:
            dict: Информация о кэше (размер, количество файлов, последнее обновление и т.д.)
        """
        info = {
            "version": CACHE_VERSION,
            "total_size_bytes": 0,
            "total_files": 0,
            "last_modified": None,
            "categories": {}
        }
        
        try:
            # Собираем информацию о всех файлах в кэше
            for root, _, files in os.walk(self.cache_dir):
                category = os.path.basename(root)
                
                if category not in info["categories"]:
                    info["categories"][category] = {
                        "size_bytes": 0,
                        "files_count": 0
                    }
                
                for file in files:
                    file_path = os.path.join(root, file)
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # Обновляем общую информацию
                    info["total_size_bytes"] += file_size
                    info["total_files"] += 1
                    
                    # Обновляем информацию о последнем изменении
                    if info["last_modified"] is None or file_time > info["last_modified"]:
                        info["last_modified"] = file_time
                    
                    # Обновляем информацию о категории
                    info["categories"][category]["size_bytes"] += file_size
                    info["categories"][category]["files_count"] += 1
            
            # Преобразуем размеры в человекочитаемый формат
            info["total_size_human"] = self._bytes_to_human_readable(info["total_size_bytes"])
            
            for category in info["categories"]:
                size_bytes = info["categories"][category]["size_bytes"]
                info["categories"][category]["size_human"] = self._bytes_to_human_readable(size_bytes)
            
            return info
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о кэше: {e}")
            return info
    
    def _bytes_to_human_readable(self, size_bytes):
        """
        Преобразует размер в байтах в человекочитаемый формат
        
        Args:
            size_bytes (int): Размер в байтах
            
        Returns:
            str: Размер в человекочитаемом формате
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024 