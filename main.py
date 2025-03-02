"""
Система интеллектуального поиска и обработки информации
"""
import os
import sys
import time
import asyncio
from datetime import datetime

from src.core.utils import logger, sanitize_filename, show_animation, print_progress
from src.search.planned_topics import TopicPlanner
from src.search.planned_searching import SearchQueryPlanner
from src.search.scraping import run_search
from src.processing.ranking_search_result import SearchResultRanker
from src.processing.summarizer import DocumentSummarizer
from src.processing.ranking_summary import SummaryRanker
from src.processing.nlp_utils import AnswerGenerator
from src.storage.cache_manager import CacheManager

def print_header():
    """
    Выводит заголовок приложения в консоль
    """
    print("\n" + "=" * 80)
    print("СИСТЕМА ИНТЕЛЛЕКТУАЛЬНОГО ПОИСКА И ОБРАБОТКИ ИНФОРМАЦИИ".center(80))
    print("=" * 80 + "\n")

def print_step(step_number, step_name):
    """
    Выводит информацию о текущем шаге обработки
    
    Args:
        step_number (int): Номер шага
        step_name (str): Название шага
    """
    print(f"\n>> Шаг {step_number}: {step_name}")
    print("-" * 50)

def get_user_query():
    """
    Получает запрос от пользователя через консоль
    
    Returns:
        str: Запрос пользователя
    """
    while True:
        query = input("\nВведите ваш запрос (или 'выход' для завершения): ").strip()
        
        if query.lower() in ["выход", "exit", "quit", "q"]:
            print("\nЗавершение работы программы...")
            sys.exit(0)
        
        if not query:
            print("Запрос не может быть пустым. Пожалуйста, попробуйте снова.")
            continue
        
        return query

def display_subtopics(subtopics):
    """
    Выводит список подзапросов в консоль и позволяет пользователю отредактировать их
    
    Args:
        subtopics (list): Список сгенерированных подзапросов
        
    Returns:
        list: Отредактированный список подзапросов
    """
    if not subtopics:
        print("Не удалось сгенерировать подзапросы для поиска.")
        return []
    
    print("\nСгенерированные подзапросы для поиска:")
    for i, subtopic in enumerate(subtopics, 1):
        print(f"{i}. {subtopic}")
    
    # Спрашиваем, хочет ли пользователь отредактировать подзапросы
    while True:
        choice = input("\nХотите отредактировать подзапросы (да/нет)? ").strip().lower()
        
        if choice in ["нет", "н", "no", "n"]:
            return subtopics
        
        if choice in ["да", "д", "yes", "y"]:
            edited_subtopics = edit_subtopics(subtopics)
            return edited_subtopics
        
        print("Пожалуйста, введите 'да' или 'нет'.")

def edit_subtopics(subtopics):
    """
    Позволяет пользователю отредактировать подзапросы
    
    Args:
        subtopics (list): Исходный список подзапросов
        
    Returns:
        list: Отредактированный список подзапросов
    """
    edited_subtopics = subtopics.copy()
    
    while True:
        print("\nВыберите действие:")
        print("1. Удалить подзапрос")
        print("2. Добавить новый подзапрос")
        print("3. Редактировать существующий подзапрос")
        print("4. Закончить редактирование")
        
        choice = input("\nВаш выбор (1-4): ").strip()
        
        if choice == "1":
            # Удаление подзапроса
            if not edited_subtopics:
                print("Список подзапросов пуст.")
                continue
            
            for i, subtopic in enumerate(edited_subtopics, 1):
                print(f"{i}. {subtopic}")
            
            idx = input("Введите номер подзапроса для удаления: ").strip()
            try:
                idx = int(idx)
                if 1 <= idx <= len(edited_subtopics):
                    removed = edited_subtopics.pop(idx - 1)
                    print(f"Подзапрос '{removed}' удален.")
                else:
                    print("Неверный номер подзапроса.")
            except ValueError:
                print("Пожалуйста, введите число.")
        
        elif choice == "2":
            # Добавление нового подзапроса
            new_subtopic = input("Введите новый подзапрос: ").strip()
            if new_subtopic:
                edited_subtopics.append(new_subtopic)
                print(f"Подзапрос '{new_subtopic}' добавлен.")
            else:
                print("Подзапрос не может быть пустым.")
        
        elif choice == "3":
            # Редактирование существующего подзапроса
            if not edited_subtopics:
                print("Список подзапросов пуст.")
                continue
            
            for i, subtopic in enumerate(edited_subtopics, 1):
                print(f"{i}. {subtopic}")
            
            idx = input("Введите номер подзапроса для редактирования: ").strip()
            try:
                idx = int(idx)
                if 1 <= idx <= len(edited_subtopics):
                    new_text = input(f"Введите новый текст для подзапроса '{edited_subtopics[idx-1]}': ").strip()
                    if new_text:
                        edited_subtopics[idx - 1] = new_text
                        print(f"Подзапрос обновлен на '{new_text}'.")
                    else:
                        print("Подзапрос не может быть пустым.")
                else:
                    print("Неверный номер подзапроса.")
            except ValueError:
                print("Пожалуйста, введите число.")
        
        elif choice == "4":
            # Завершение редактирования
            if not edited_subtopics:
                print("Предупреждение: список подзапросов пуст. Поиск не будет выполнен.")
            return edited_subtopics
        
        else:
            print("Неверный выбор. Пожалуйста, выберите 1, 2, 3 или 4.")

async def main():
    """
    Основная функция программы
    """
    # Создаем директорию для кэширования результатов поиска
    os.makedirs("cache", exist_ok=True)
    
    print_header()
    
    # Проверяем наличие API ключа
    if not os.getenv("AITUNNEL_API_KEY"):
        print("ОШИБКА: API ключ не найден. Пожалуйста, установите переменную окружения AITUNNEL_API_KEY.")
        print("Пример: export AITUNNEL_API_KEY=sk-aitunnel-xxx")
        return
    
    # Создаем менеджер кэша
    cache_manager = CacheManager()
    
    while True:
        try:
            # Шаг 1: Получение запроса от пользователя
            print_step(1, "Ввод запроса")
            query = get_user_query()
            
            # Генерируем имя темы для кэширования
            theme_name = cache_manager.generate_theme_name(query)
            
            # Шаг 2: Генерация подзапросов
            print_step(2, "Генерация подзапросов")
            topic_planner = TopicPlanner()
            subtopics = topic_planner.generate_subtopics(query)
            
            # Шаг 3: Отображение и редактирование подзапросов
            print_step(3, "Просмотр и редактирование подзапросов")
            final_subtopics = display_subtopics(subtopics)
            
            if not final_subtopics:
                print("Список подзапросов пуст. Поиск не будет выполнен.")
                continue
            
            # Сохраняем подзапросы в файл
            subtopics_file = topic_planner.save_subtopics_to_file(final_subtopics, query, theme_name)
            
            # Шаг 4: Генерация поисковых запросов для каждого подзапроса
            print_step(4, "Генерация поисковых запросов")
            search_query_planner = SearchQueryPlanner()
            
            print("Генерация поисковых запросов для каждого подзапроса...")
            search_queries_dict = search_query_planner.generate_all_search_queries(final_subtopics)
            
            # Сохраняем поисковые запросы в файл
            search_queries_file = search_query_planner.save_search_queries_to_file(search_queries_dict, theme_name)
            
            # Шаг 5: Выполнение поиска
            print_step(5, "Выполнение поиска")
            print(f"Выполняем поиск по {len(final_subtopics)} подзапросам...")
            
            # Анимация поиска
            show_animation()
            
            # Выполняем поиск асинхронно
            search_results = await run_search(search_queries_dict, theme_name)
            
            if not search_results:
                print("Не удалось выполнить поиск. Пожалуйста, проверьте подключение к интернету и попробуйте снова.")
                continue
            
            # Шаг 6: Ранжирование результатов поиска
            print_step(6, "Ранжирование результатов поиска")
            search_result_ranker = SearchResultRanker()
            
            # Обрабатываем результаты поиска: фильтруем дубликаты, ранжируем и выбираем топ-5
            top_results = search_result_ranker.process_search_results(search_results, query)
            
            # Сохраняем отранжированные результаты
            ranked_results_file = search_result_ranker.save_ranked_results_to_json(top_results, theme_name)
            
            print(f"Найдено и отранжировано {len(top_results)} результатов.")
            
            # Шаг 7: Саммаризация документов
            print_step(7, "Саммаризация документов")
            document_summarizer = DocumentSummarizer()
            
            print("Выполняем саммаризацию документов...")
            documents_with_summaries = document_summarizer.process_documents(top_results, theme_name)
            
            # Шаг 8: Ранжирование саммари
            print_step(8, "Ранжирование саммари")
            summary_ranker = SummaryRanker()
            
            # Обрабатываем саммари: ранжируем и выбираем топ-5
            top_summaries = summary_ranker.process_summaries(documents_with_summaries, query)
            
            # Сохраняем отранжированные саммари
            ranked_summaries_file = summary_ranker.save_ranked_summaries_to_json(top_summaries, theme_name)
            
            print(f"Отранжировано {len(top_summaries)} саммари.")
            
            # Шаг 9: Генерация ответа
            print_step(9, "Генерация ответа")
            answer_generator = AnswerGenerator()
            
            print("Генерация структурированного ответа...")
            answer = answer_generator.generate_answer(top_summaries, query)
            
            if answer:
                # Сохраняем запрос и ответ в файлы
                request_file = answer_generator.save_request_to_file(query, theme_name)
                answer_file = answer_generator.save_answer_to_file(answer, query, theme_name)
                
                print("\nОтвет успешно сгенерирован!")
                print(f"Ответ сохранен в файл: {answer_file}")
                
                # Выводим ответ в консоль
                print("\n" + "=" * 80)
                print("ОТВЕТ НА ЗАПРОС".center(80))
                print("=" * 80 + "\n")
                print(answer)
                print("\n" + "=" * 80 + "\n")
            else:
                print("Не удалось сгенерировать ответ.")
            
            # Спрашиваем, хочет ли пользователь продолжить работу с программой
            while True:
                continue_choice = input("\nХотите выполнить новый поиск (да/нет)? ").strip().lower()
                
                if continue_choice in ["нет", "н", "no", "n"]:
                    print("\nЗавершение работы программы...")
                    return
                
                if continue_choice in ["да", "д", "yes", "y"]:
                    break
                
                print("Пожалуйста, введите 'да' или 'нет'.")
                
        except KeyboardInterrupt:
            print("\nПрограмма прервана пользователем.")
            return
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
            print(f"\nПроизошла ошибка: {e}")
            print("Пожалуйста, попробуйте снова.")

if __name__ == "__main__":
    # Запуск основной функции с асинхронной поддержкой
    asyncio.run(main())
