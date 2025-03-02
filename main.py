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
from src.search.scraping import run_search, scrape_top_ranked_results
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
            
            # Информация о лимитах API
            print("\nВажно: Поиск может занять некоторое время из-за ограничений API:")
            print("- SearchXNG: до 10 запросов в минуту")
            print("- r.jina.ai: до 5 запросов в секунду (для получения Markdown-представления страниц)")
            print("- AITUNNEL: до 2 запросов в секунду (для рейтинга и саммаризации)\n")
            
            # Анимация поиска
            show_animation()
            
            # Выполняем поиск асинхронно (на этом этапе только получаем результаты поиска без скрапинга)
            search_results = await run_search(search_queries_dict, theme_name)
            
            if not search_results:
                print("Не удалось выполнить поиск. Пожалуйста, проверьте подключение к интернету и попробуйте снова.")
                continue
            
            # Шаг 6: Ранжирование результатов поиска с использованием LLM
            print_step(6, "Ранжирование результатов поиска с помощью языковой модели")
            search_result_ranker = SearchResultRanker()
            
            print("Оценка результатов поиска по 5 критериям с помощью языковой модели:")
            print("1. Соответствие исходному запросу")
            print("2. Соответствие направлению поиска (подзапросу)")
            print("3. Полнота информации")
            print("4. Точность данных")
            print("5. Читабельность и структура")
            
            # Ранжируем результаты поиска
            ranked_results = search_result_ranker.process_search_results(search_results, query)
            
            # Сохраняем отранжированные результаты
            ranked_results_file = search_result_ranker.save_ranked_results_to_json(ranked_results, theme_name)
            
            # Шаг 7: Скрапинг содержимого топ-5 страниц
            print_step(7, "Скрапинг содержимого топ-5 страниц")
            print("Скрапинг содержимого только для 5 наиболее релевантных результатов...")
            
            # Выполняем скрапинг только для топ-5 отранжированных результатов
            top_results_with_content = await scrape_top_ranked_results(ranked_results[:5], theme_name)
            
            if not top_results_with_content:
                print("Не удалось получить содержимое страниц. Проверьте подключение к интернету и попробуйте снова.")
                continue
            
            # Шаг 8: Саммаризация документов
            print_step(8, "Саммаризация документов")
            document_summarizer = DocumentSummarizer()
            
            summaries = []
            
            print(f"Создание саммари для {len(top_results_with_content)} документов...")
            for i, result in enumerate(top_results_with_content, 1):
                title = result.get("title", "")
                content = result.get("content", "")
                url = result.get("url", "")
                
                print(f"[{i}/{len(top_results_with_content)}] Саммаризация: {title[:50]}...", end="\r")
                
                summary = document_summarizer.create_summary(content, title, url, query, theme_name)
                if summary:
                    summaries.append(summary)
            
            print(f"\nСоздано {len(summaries)} саммари.")
            
            # Шаг 9: Ранжирование саммари
            print_step(9, "Ранжирование саммари")
            summary_ranker = SummaryRanker()
            
            print("Оценка саммари по 5 критериям с помощью языковой модели:")
            print("1. Соответствие исходному запросу")
            print("2. Полнота информации")
            print("3. Точность информации")
            print("4. Информативность")
            print("5. Читабельность и структура")
            
            # Ранжируем саммари
            ranked_summaries = summary_ranker.rank_summaries(summaries, query, theme_name)
            
            # Шаг 10: Генерация итогового ответа
            print_step(10, "Генерация итогового ответа")
            answer_generator = AnswerGenerator()
            
            # Выбираем топ-5 наиболее релевантных саммари для генерации ответа
            top_summaries = ranked_summaries[:5]
            
            print(f"Генерация ответа на основе {len(top_summaries)} наиболее релевантных саммари...")
            answer = answer_generator.generate_answer(query, top_summaries, theme_name)
            
            # Выводим итоговый ответ
            print("\n" + "=" * 80)
            print("ИТОГОВЫЙ ОТВЕТ:".center(80))
            print("=" * 80 + "\n")
            
            print(answer)
            
            # Спрашиваем пользователя о дальнейших действиях
            print("\n" + "=" * 80)
            input("\nНажмите Enter для продолжения...")
            
        except KeyboardInterrupt:
            print("\n\nРабота программы прервана пользователем.")
            break
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
            print(f"\nПроизошла ошибка: {e}")
            print("Пожалуйста, попробуйте снова или проверьте логи для получения дополнительной информации.")
            input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nРабота программы прервана пользователем.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"\nКритическая ошибка: {e}")
        print("Пожалуйста, проверьте логи для получения дополнительной информации.")
