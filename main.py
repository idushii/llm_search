import os
import sys
import time
from datetime import datetime
from planned import QueryPlanner
from scraping import run_search

def print_header():
    """
    Выводит заголовок приложения в консоль
    """
    print("\n" + "=" * 80)
    print("СЕРВИС ИТЕРАТИВНОГО ПОИСКА ИНФОРМАЦИИ".center(80))
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

def generate_output_filename(query):
    """
    Генерирует имя файла для сохранения результатов
    
    Args:
        query (str): Запрос пользователя
        
    Returns:
        str: Имя файла
    """
    # Генерируем имя файла на основе запроса и текущей даты/времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_query = "".join(c if c.isalnum() else "_" for c in query)
    sanitized_query = sanitized_query[:30]  # Ограничиваем длину
    
    return f"results_{sanitized_query}_{timestamp}.md"

def display_topics(topics):
    """
    Выводит список тем в консоль и позволяет пользователю отредактировать их
    
    Args:
        topics (list): Список сгенерированных тем
        
    Returns:
        list: Отредактированный список тем
    """
    if not topics:
        print("Не удалось сгенерировать темы для поиска.")
        return []
    
    print("\nСгенерированные темы для поиска:")
    for i, topic in enumerate(topics, 1):
        print(f"{i}. {topic}")
    
    # Спрашиваем, хочет ли пользователь отредактировать темы
    while True:
        choice = input("\nХотите отредактировать темы (да/нет)? ").strip().lower()
        
        if choice in ["нет", "н", "no", "n"]:
            return topics
        
        if choice in ["да", "д", "yes", "y"]:
            edited_topics = edit_topics(topics)
            return edited_topics
        
        print("Пожалуйста, введите 'да' или 'нет'.")

def edit_topics(topics):
    """
    Позволяет пользователю отредактировать темы
    
    Args:
        topics (list): Исходный список тем
        
    Returns:
        list: Отредактированный список тем
    """
    edited_topics = topics.copy()
    
    while True:
        print("\nВыберите действие:")
        print("1. Удалить тему")
        print("2. Добавить новую тему")
        print("3. Редактировать существующую тему")
        print("4. Закончить редактирование")
        
        choice = input("\nВаш выбор (1-4): ").strip()
        
        if choice == "1":
            # Удаление темы
            if not edited_topics:
                print("Список тем пуст.")
                continue
            
            for i, topic in enumerate(edited_topics, 1):
                print(f"{i}. {topic}")
            
            idx = input("Введите номер темы для удаления: ").strip()
            try:
                idx = int(idx)
                if 1 <= idx <= len(edited_topics):
                    removed = edited_topics.pop(idx - 1)
                    print(f"Тема '{removed}' удалена.")
                else:
                    print("Неверный номер темы.")
            except ValueError:
                print("Пожалуйста, введите число.")
        
        elif choice == "2":
            # Добавление новой темы
            new_topic = input("Введите новую тему: ").strip()
            if new_topic:
                edited_topics.append(new_topic)
                print(f"Тема '{new_topic}' добавлена.")
            else:
                print("Тема не может быть пустой.")
        
        elif choice == "3":
            # Редактирование существующей темы
            if not edited_topics:
                print("Список тем пуст.")
                continue
            
            for i, topic in enumerate(edited_topics, 1):
                print(f"{i}. {topic}")
            
            idx = input("Введите номер темы для редактирования: ").strip()
            try:
                idx = int(idx)
                if 1 <= idx <= len(edited_topics):
                    new_text = input(f"Введите новый текст для темы '{edited_topics[idx-1]}': ").strip()
                    if new_text:
                        edited_topics[idx - 1] = new_text
                        print(f"Тема обновлена на '{new_text}'.")
                    else:
                        print("Тема не может быть пустой.")
                else:
                    print("Неверный номер темы.")
            except ValueError:
                print("Пожалуйста, введите число.")
        
        elif choice == "4":
            # Завершение редактирования
            if not edited_topics:
                print("Предупреждение: список тем пуст. Поиск не будет выполнен.")
            return edited_topics
        
        else:
            print("Неверный выбор. Пожалуйста, выберите 1, 2, 3 или 4.")

def show_searching_animation(duration=0.5):
    """
    Показывает анимацию во время поиска
    
    Args:
        duration (float): Продолжительность каждого шага анимации в секундах
    """
    chars = ["|", "/", "-", "\\"]
    for _ in range(3):
        for char in chars:
            sys.stdout.write(f"\rВыполняется поиск {char}")
            sys.stdout.flush()
            time.sleep(duration)

def main():
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
    
    while True:
        try:
            # Шаг 1: Получение запроса от пользователя
            print_step(1, "Ввод запроса")
            query = get_user_query()
            
            # Шаг 2: Генерация тем для поиска
            print_step(2, "Генерация тем для поиска")
            planner = QueryPlanner()
            topics = planner.generate_search_topics(query)
            
            # Шаг 3: Отображение и редактирование тем
            print_step(3, "Просмотр и редактирование тем")
            final_topics = display_topics(topics)
            
            if not final_topics:
                print("Список тем пуст. Поиск не будет выполнен.")
                continue
            
            # Шаг 4: Выполнение поиска
            print_step(4, "Выполнение поиска и обработка результатов")
            output_file = generate_output_filename(query)
            print(f"Начинаем поиск по {len(final_topics)} темам...")
            
            show_searching_animation()
            
            # Выполняем поиск
            topics_file, results_json, results_md = run_search(final_topics, query, output_file)
            
            if topics_file and results_json:
                print(f"\nПоиск завершен! Результаты сохранены:")
                print(f"1. Список тем: {os.path.abspath(topics_file)}")
                print(f"2. Результаты поиска (JSON): {os.path.abspath(results_json)}")
                print(f"3. Результаты поиска (Markdown): {os.path.abspath(results_md)}")
                print(f"4. Отдельные страницы сохранены в директории: {os.path.abspath('cache')}")
            else:
                print("\nПроизошла ошибка при выполнении поиска.")
            
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
            print("\nРабота программы прервана пользователем.")
            return
        
        except Exception as e:
            print(f"\nПроизошла непредвиденная ошибка: {e}")
            print("Программа будет перезапущена.")
            continue


if __name__ == "__main__":
    main()
