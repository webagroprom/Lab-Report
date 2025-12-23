#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import pandas as pd
import os
import json
from werkzeug.utils import secure_filename
import traceback
import re
import datetime
from collections import defaultdict, Counter

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/www/survey-report/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_database():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT UNIQUE,
            response_count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_category TEXT,
            question_text TEXT,
            answer_text TEXT,
            answer_value INTEGER,
            count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_type TEXT,
            count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS satisfaction_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            score INTEGER,
            count INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    conn.row_factory = sqlite3.Row
    return conn

def parse_correct_json_data(json_data):
    """Исправленный парсер для точного извлечения данных"""
    location_stats = Counter()
    question_stats = defaultdict(Counter)
    problem_stats = Counter()
    satisfaction_stats = Counter()
    comments_stats = defaultdict(list)  # Для комментариев
    
    print(f"Обработка {len(json_data)} ответов...")
    
    for respondent_idx, respondent_data in enumerate(json_data):
        current_location = None
        
        for item in respondent_data:
            if len(item) < 2:
                continue
                
            question = item[0]
            answer = item[1]
            
            if not isinstance(question, str):
                continue
            
            question_lower = question.lower().strip()
            
            # 1. ЛОКАЦИЯ
            if "локацию" in question_lower or "локация" in question_lower or "вашу локацию" in question_lower:
                if answer and isinstance(answer, str) and answer.strip():
                    location = answer.strip()
                    location_stats[location] += 1
                    current_location = location
                elif answer:
                    location = str(answer).strip()
                    location_stats[location] += 1
                    current_location = location
                else:
                    location_stats["Не указана"] += 1
                    current_location = "Не указана"
            
            # 2. ОЦЕНКИ (формат: "2 - Приемлемо", "3 - Хорошо" и т.д.)
            elif "оцените" in question_lower or "удовлетворены" in question_lower or "оцениваете" in question_lower:
                if answer and isinstance(answer, str) and answer.strip():
                    # Определяем категорию вопроса
                    if "скорость" in question_lower or "быстроту" in question_lower:
                        category = "Скорость загрузки"
                        question_stats[category][answer] += 1
                    
                    elif "стабильность" in question_lower or "зависаний" in question_lower:
                        category = "Стабильность работы"
                        question_stats[category][answer] += 1
                    
                    elif "монитора" in question_lower or "экрана" in question_lower or "контрастный" in question_lower:
                        category = "Удобство монитора"
                        question_stats[category][answer] += 1
                    
                    elif "яндекс" in question_lower:
                        category = "Приложения Яндекс"
                        question_stats[category][answer] += 1
                    
                    elif "ms office" in question_lower or "офис" in question_lower:
                        category = "MS Office"
                        question_stats[category][answer] += 1
                    
                    elif "1с" in question_lower:
                        category = "1С"
                        question_stats[category][answer] += 1
                    
                    elif "bitrix24" in question_lower:
                        category = "Bitrix24"
                        question_stats[category][answer] += 1
                    
                    elif "сторонних приложений" in question_lower:
                        category = "Сторонние приложения"
                        question_stats[category][answer] += 1
                    
                    elif "обновлений" in question_lower:
                        category = "Обновления ПО"
                        question_stats[category][answer] += 1
            
            # 3. ПРОБЛЕМЫ (отдельный раздел "С какими проблемами...")
            elif "проблемами" in question_lower and "сталкиваетесь" in question_lower:
                if answer and isinstance(answer, str) and answer.strip():
                    # Определяем тип проблемы по подвопросу
                    if "зависание компьютера" in question_lower:
                        problem_stats["Зависание компьютера"] += 1
                    elif "медленная работа программ" in question_lower:
                        problem_stats["Медленная работа программ"] += 1
                    elif "сбои в работе офисных приложений" in question_lower:
                        problem_stats["Сбои в работе офисных приложений"] += 1
                    elif "проблемы с печатью" in question_lower:
                        problem_stats["Проблемы с печатью"] += 1
                    elif "сложности с сетевыми дисками" in question_lower:
                        problem_stats["Сложности с сетевыми дисками"] += 1
            
            # 4. ОБЩАЯ УДОВЛЕТВОРЕННОСТЬ (числовая)
            elif "общая удовлетворенность" in question_lower:
                if answer:
                    try:
                        if isinstance(answer, str):
                            match = re.search(r'(\d+)', answer)
                            if match:
                                score = int(match.group(1))
                                if 1 <= score <= 10:
                                    satisfaction_stats[score] += 1
                            elif answer.strip().isdigit():
                                score = int(answer.strip())
                                if 1 <= score <= 10:
                                    satisfaction_stats[score] += 1
                        else:
                            score = int(answer)
                            if 1 <= score <= 10:
                                satisfaction_stats[score] += 1
                    except:
                        pass
            
            # 5. КОММЕНТАРИИ (пропускаем для статистики оценок)
            elif "предложения" in question_lower or "дополнительные приложения" in question_lower or "какие дополнительные" in question_lower:
                # Это комментарии, не включаем в статистику оценок
                continue
    
    print(f"Локаций: {len(location_stats)}")
    print(f"Категорий вопросов: {len(question_stats)}")
    print(f"Типов проблем: {len(problem_stats)}")
    print(f"Оценок удовлетворенности: {len(satisfaction_stats)}")
    
    # Выводим отладочную информацию
    for category, answers in question_stats.items():
        print(f"\n{category}:")
        for answer, count in answers.most_common(5):
            print(f"  {answer}: {count}")
    
    return {
        'locations': location_stats,
        'questions': question_stats,
        'problems': problem_stats,
        'satisfaction': satisfaction_stats,
        'total_respondents': len(json_data)
    }

def save_correct_data(parsed_data):
    """Сохраняет исправленные данные"""
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    try:
        # Очищаем
        cursor.execute("DELETE FROM locations")
        cursor.execute("DELETE FROM question_responses")
        cursor.execute("DELETE FROM problem_responses")
        cursor.execute("DELETE FROM satisfaction_scores")
        conn.commit()
        
        # Локации
        for location, count in parsed_data['locations'].items():
            if location and location != "Не указана" and count > 0:
                cursor.execute('''
                    INSERT INTO locations (location_name, response_count)
                    VALUES (?, ?)
                ''', (location, count))
        
        # Вопросы (только числовые оценки)
        for category, answers in parsed_data['questions'].items():
            for answer_text, count in answers.items():
                if answer_text and count > 0:
                    # Извлекаем числовое значение из ответа
                    value = None
                    match = re.search(r'^(\d+)', answer_text.strip())
                    if match:
                        value = int(match.group(1))
                    
                    # Фильтруем только числовые оценки
                    if value is not None and 1 <= value <= 5:
                        cursor.execute('''
                            INSERT INTO question_responses (question_category, question_text, answer_text, answer_value, count)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (category, category, answer_text, value, count))
        
        # Проблемы
        for problem, count in parsed_data['problems'].items():
            if problem and count > 0:
                cursor.execute('''
                    INSERT INTO problem_responses (problem_type, count)
                    VALUES (?, ?)
                ''', (problem, count))
        
        # Удовлетворенность
        for score, count in parsed_data['satisfaction'].items():
            if score > 0 and count > 0:
                cursor.execute('''
                    INSERT INTO satisfaction_scores (score, count)
                    VALUES (?, ?)
                ''', (score, count))
        
        conn.commit()
        return True, None
        
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# Маршруты остаются прежними, но используем новые функции
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Общее количество по локациям
        cursor.execute("SELECT SUM(response_count) FROM locations")
        total_responses_row = cursor.fetchone()
        total_responses = total_responses_row[0] if total_responses_row and total_responses_row[0] else 0
        
        # Локации
        cursor.execute('SELECT location_name, response_count FROM locations ORDER BY response_count DESC')
        locations = []
        for row in cursor.fetchall():
            percent = (row['response_count'] / total_responses * 100) if total_responses > 0 else 0
            locations.append({
                'name': row['location_name'],
                'count': row['response_count'],
                'percent': round(percent, 1)
            })
        
        # Вопросы (группируем по категории)
        cursor.execute('''
            SELECT question_category, question_text, answer_text, answer_value, SUM(count) as total_count
            FROM question_responses 
            GROUP BY question_category, answer_text
            ORDER BY question_category, total_count DESC
        ''')
        
        questions_by_category = defaultdict(list)
        category_totals = defaultdict(int)
        
        for row in cursor.fetchall():
            questions_by_category[row['question_category']].append({
                'text': row['answer_text'],
                'count': row['total_count'],
                'value': row['answer_value']
            })
            category_totals[row['question_category']] += row['total_count']
        
        questions_sections = []
        question_titles = {
            'Скорость загрузки': 'Оцените скорость загрузки системы',
            'Стабильность работы': 'Оцените стабильность работы системы', 
            'Удобство монитора': 'Оцените удобство использования монитора',
            'Приложения Яндекс': 'Приложения Яндекс',
            'MS Office': 'MS Office',
            '1С': '1С',
            'Bitrix24': 'Bitrix24',
            'Сторонние приложения': 'Сторонние приложения',
            'Обновления ПО': 'Обновления ПО'
        }
        
        for category, answers in questions_by_category.items():
            total = category_totals.get(category, 0)
            
            # Добавляем проценты и сортируем по значению
            for answer in answers:
                answer['percent'] = round((answer['count'] / total * 100), 1) if total > 0 else 0
            
            # Сортируем по значению (3, 2, 1)
            answers.sort(key=lambda x: x.get('value', 0), reverse=True)
            
            title = question_titles.get(category, category)
            questions_sections.append({
                'title': title,
                'subtitle': '',
                'total': total,
                'answers': answers[:10]  # Ограничиваем 10 ответами
            })
        
        # Проблемы
        cursor.execute('SELECT problem_type, count FROM problem_responses ORDER BY count DESC')
        problems = []
        total_problems = 0
        for row in cursor.fetchall():
            problems.append({
                'text': row['problem_type'],
                'count': row['count']
            })
            total_problems += row['count']
        
        if problems:
            for problem in problems:
                problem['percent'] = round((problem['count'] / total_problems * 100), 1) if total_problems > 0 else 0
            
            questions_sections.append({
                'title': 'С какими проблемами вы сталкиваетесь чаще всего?',
                'subtitle': '',
                'total': total_problems,
                'answers': problems
            })
        
        # Удовлетворенность
        cursor.execute('SELECT score, count FROM satisfaction_scores ORDER BY score')
        satisfaction = []
        total_satisfaction = 0
        for row in cursor.fetchall():
            satisfaction.append({
                'text': str(row['score']),
                'count': row['count']
            })
            total_satisfaction += row['count']
        
        if satisfaction:
            for item in satisfaction:
                item['percent'] = round((item['count'] / total_satisfaction * 100), 1) if total_satisfaction > 0 else 0
            
            questions_sections.append({
                'title': 'Общая удовлетворенность рабочего места',
                'subtitle': '',
                'total': total_satisfaction,
                'answers': satisfaction
            })
        
        return render_template('dashboard_full.html',
                             total_responses=total_responses,
                             location_stats={
                                 'total': total_responses,
                                 'locations': locations
                             },
                             questions=questions_sections,
                             update_time=datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))
                             
    except Exception as e:
        print(f"Dashboard error: {e}")
        traceback.print_exc()
        return render_template('dashboard_full.html',
                             total_responses=0,
                             location_stats={'total': 0, 'locations': []},
                             questions=[],
                             update_time=datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))
    finally:
        conn.close()

@app.route('/import')
def import_page():
    return render_template('import_simple.html')

@app.route('/import_json', methods=['POST'])
def handle_import_json():
    if 'json_file' not in request.files:
        return render_template('import_simple.html', 
                             message='Файл не выбран',
                             message_type='error')
    
    file = request.files['json_file']
    if file.filename == '':
        return render_template('import_simple.html',
                             message='Файл не выбран',
                             message_type='error')
    
    if file and file.filename.endswith('.json'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            print(f"Загружен JSON с {len(json_data)} ответами")
            
            # Используем исправленный парсер
            parsed_data = parse_correct_json_data(json_data)
            
            # Сохраняем
            success, error = save_correct_data(parsed_data)
            
            if not success:
                return render_template('import_simple.html',
                                     message=f'Ошибка сохранения: {error}',
                                     message_type='error')
            else:
                return render_template('import_simple.html',
                                     message=f'Успешно импортировано {parsed_data["total_respondents"]} ответов',
                                     message_type='success')
        
        except Exception as e:
            return render_template('import_simple.html',
                                 message=f'Ошибка обработки файла: {str(e)}',
                                 message_type='error',
                                 details=traceback.format_exc())
    
    return render_template('import_simple.html',
                         message='Неверный формат файла. Требуется JSON',
                         message_type='error')

# Простые маршруты
@app.route('/locations')
def locations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT location_name, response_count FROM locations ORDER BY response_count DESC')
    locations = cursor.fetchall()
    conn.close()
    return render_template('simple_locations.html', locations=locations)

@app.route('/questions')
def questions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT question_category, answer_text, SUM(count) as total_count
        FROM question_responses 
        GROUP BY question_category, answer_text
        ORDER BY question_category, total_count DESC
    ''')
    questions_data = cursor.fetchall()
    conn.close()
    return render_template('simple_questions.html', questions=questions_data)

if __name__ == '__main__':
    init_database()
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
