"""
Модуль для работы с файловой системой
"""
import os
import json
import shutil
import zipfile
import glob
from datetime import datetime

from src.core.utils import logger, create_directory
from src.core.config import CACHE_DIR

class FileSystemManager:
    """
    Класс для управления файловой системой проекта
    """
    def __init__(self, cache_dir=None):
        """
        Инициализирует менеджер файловой системы
        
        Args:
            cache_dir (str, optional): Путь к директории кэша. По умолчанию используется CACHE_DIR из config.py
        """
        self.cache_dir = cache_dir or CACHE_DIR
        create_directory(self.cache_dir)
    
    def export_cache(self, export_path=None, theme_name=None):
        """
        Экспортирует кэш в ZIP-архив
        
        Args:
            export_path (str, optional): Путь для сохранения архива. По умолчанию текущая директория.
            theme_name (str, optional): Название темы для экспорта. Если не указано, экспортируется весь кэш.
            
        Returns:
            str: Путь к созданному архиву или None в случае ошибки
        """
        try:
            # Если путь для экспорта не указан, используем текущую директорию
            if not export_path:
                export_path = os.getcwd()
            
            # Генерируем имя файла с текущей датой/временем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if theme_name:
                archive_name = f"cache_{theme_name}_{timestamp}.zip"
                # Проверяем существование директории темы
                theme_dir = os.path.join(self.cache_dir, theme_name)
                if not os.path.exists(theme_dir):
                    logger.error(f"Директория темы не существует: {theme_dir}")
                    return None
                source_dir = theme_dir
            else:
                archive_name = f"cache_full_{timestamp}.zip"
                source_dir = self.cache_dir
            
            # Путь к архиву
            archive_path = os.path.join(export_path, archive_name)
            
            # Создаем архив
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Получаем относительный путь для сохранения структуры директорий
                        arcname = os.path.relpath(file_path, source_dir if theme_name else os.path.dirname(self.cache_dir))
                        zipf.write(file_path, arcname)
            
            logger.info(f"Кэш успешно экспортирован в архив: {archive_path}")
            return archive_path
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте кэша: {e}")
            return None
    
    def import_cache(self, archive_path, theme_name=None):
        """
        Импортирует кэш из ZIP-архива
        
        Args:
            archive_path (str): Путь к ZIP-архиву
            theme_name (str, optional): Название темы для импорта. Если не указано, импортируется весь кэш.
            
        Returns:
            bool: True в случае успеха, False в случае ошибки
        """
        try:
            # Проверяем существование архива
            if not os.path.exists(archive_path):
                logger.error(f"Архив не найден: {archive_path}")
                return False
            
            # Определяем директорию для импорта
            if theme_name:
                target_dir = os.path.join(self.cache_dir, theme_name)
            else:
                target_dir = self.cache_dir
            
            # Создаем директорию, если она не существует
            create_directory(target_dir)
            
            # Извлекаем архив
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(target_dir)
            
            logger.info(f"Кэш успешно импортирован из архива: {archive_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при импорте кэша: {e}")
            return False
    
    def list_themes(self):
        """
        Возвращает список тем в кэше
        
        Returns:
            list: Список названий тем
        """
        try:
            themes = []
            
            # Получаем список директорий в кэше
            for item in os.listdir(self.cache_dir):
                item_path = os.path.join(self.cache_dir, item)
                
                # Если это директория и содержит answers.md, считаем её темой
                if os.path.isdir(item_path):
                    # Проверяем наличие файлов запроса/ответа
                    request_path = os.path.join(item_path, "request.md")
                    answer_path = os.path.join(item_path, "answer.md")
                    
                    if os.path.exists(request_path) or os.path.exists(answer_path):
                        themes.append(item)
            
            return themes
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка тем: {e}")
            return []
    
    def get_theme_info(self, theme_name):
        """
        Возвращает информацию о конкретной теме
        
        Args:
            theme_name (str): Название темы
            
        Returns:
            dict: Информация о теме (запрос, дата создания, и т.д.) или None в случае ошибки
        """
        try:
            theme_dir = os.path.join(self.cache_dir, theme_name)
            
            # Проверяем существование директории темы
            if not os.path.exists(theme_dir):
                logger.error(f"Директория темы не существует: {theme_dir}")
                return None
            
            info = {
                "name": theme_name,
                "created": None,
                "request": None,
                "answer": None,
                "has_subtopics": False,
                "has_summaries": False,
                "files_count": 0
            }
            
            # Получаем дату создания директории
            theme_stat = os.stat(theme_dir)
            info["created"] = datetime.fromtimestamp(theme_stat.st_ctime)
            
            # Проверяем наличие файлов запроса/ответа
            request_path = os.path.join(theme_dir, "request.md")
            answer_path = os.path.join(theme_dir, "answer.md")
            
            if os.path.exists(request_path):
                with open(request_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Извлекаем запрос из файла (убираем заголовок)
                    if "# Запрос" in content:
                        info["request"] = content.split("# Запрос")[1].strip()
                    else:
                        info["request"] = content.strip()
            
            if os.path.exists(answer_path):
                info["answer"] = True
            
            # Проверяем наличие подзапросов
            subtopics_path = os.path.join(self.cache_dir, f"subtopics_{theme_name}.md")
            if os.path.exists(subtopics_path):
                info["has_subtopics"] = True
            
            # Проверяем наличие саммари
            summaries_dir = os.path.join(self.cache_dir, "summaries", theme_name)
            if os.path.exists(summaries_dir) and os.listdir(summaries_dir):
                info["has_summaries"] = True
            
            # Подсчитываем количество файлов
            for root, _, files in os.walk(theme_dir):
                info["files_count"] += len(files)
            
            return info
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о теме: {e}")
            return None
    
    def delete_theme(self, theme_name):
        """
        Удаляет тему и все связанные с ней файлы
        
        Args:
            theme_name (str): Название темы
            
        Returns:
            bool: True в случае успеха, False в случае ошибки
        """
        try:
            # Удаляем все файлы и директории, связанные с темой
            paths_to_check = [
                os.path.join(self.cache_dir, theme_name),  # Основная директория темы
                os.path.join(self.cache_dir, "docs", theme_name),  # Документы
                os.path.join(self.cache_dir, "summaries", theme_name),  # Саммари
                os.path.join(self.cache_dir, "search_queries", f"{theme_name}.json"),  # Поисковые запросы
                os.path.join(self.cache_dir, "search_results", f"{theme_name}.json"),  # Результаты поиска
                os.path.join(self.cache_dir, "ranked_results", f"{theme_name}.json"),  # Ранжированные результаты
                os.path.join(self.cache_dir, "ranked_summaries", f"{theme_name}.json"),  # Ранжированные саммари
                os.path.join(self.cache_dir, f"subtopics_{theme_name}.md")  # Файл подзапросов
            ]
            
            # Удаляем все существующие файлы и директории
            for path in paths_to_check:
                if os.path.exists(path):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        logger.debug(f"Удалена директория: {path}")
                    else:
                        os.remove(path)
                        logger.debug(f"Удален файл: {path}")
            
            logger.info(f"Тема успешно удалена: {theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении темы: {e}")
            return False 