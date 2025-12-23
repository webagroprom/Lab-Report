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
            question_text TEXT,
            answer_text TEXT,
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

def parse_custom_json_data(json_data):
    """Специальный парсер для вашего формата JSON"""
    # Статистика
    location_stats = Counter()
    question_stats = defaultdict(Counter)
    problem_stats = Counter()
    satisfaction_stats = Counter()
    
    total_respondents = len(json_data)
    
    print(f"Обработка {total_respondents} ответов...")
    
    for respondent_idx, respondent_data in enumerate(json_data):
        current_location = None
        
        for item in respondent_data:
            if len(item) < 2:
                continue
                
            question = item[0]
            answer = item[1]
            
            if not isinstance(question, str):
                continue
            
            # Локация
            if "локацию" in question.lower() or "локация" in question.lower():
                if answer and isinstance(answer, str) and answer.strip():
                    location = answer.strip()
                    location_stats[location] += 1
                    current_location = location
                else:
                    location_stats["Не указана"] += 1
                    current_location = "Не указана"
            
            # Скорость загрузки
            elif "скорость загрузки" in question.lower() or "быстроту запуска" in question.lower():
                if answer:
                    question_stats["Скорость загрузки системы"][answer] += 1
            
            # Стабильность работы
            elif "стабильность работы" in question.lower() or "отсутствие зависаний" in question.lower():
                if answer:
                    question_stats["Стабильность работы системы"][answer] += 1
            
            # Удобство монитора
            elif "удобство использования монитора" in question.lower() or "контрастный, светлый" in question.lower():
                if answer:
                    question_stats["Удобство монитора"][answer] += 1
            
            # Приложения Яндекс
            elif "яндекс" in question.lower():
                if answer:
                    question_stats["Приложения Яндекс"][answer] += 1
            
            # MS Office
            elif "ms office" in question.lower() or "офис" in question.lower():
                if answer:
                    question_stats["MS Office"][answer] += 1
            
            # 1С
            elif "1с" in question.lower():
                if answer:
                    question_stats["1С"][answer] += 1
            
            # Bitrix24
            elif "bitrix24" in question.lower():
                if answer:
                    question_stats["Bitrix24"][answer] += 1
            
            # Сторонние приложения
            elif "сторонних приложений" in question.lower():
                if answer:
                    question_stats["Сторонние приложения"][answer] += 1
            
            # Обновления
            elif "обновлений" in question.lower():
                if answer:
                    question_stats["Обновления ПО"][answer] += 1
            
            # Проблемы
            elif "проблемами" in question.lower() or "проблемы" in question.lower():
                if answer and isinstance(answer, str) and answer.strip():
                    problem_text = answer.strip()
                    # Определяем тип проблемы
                    if "зависание" in question.lower():
                        problem_stats["Зависание компьютера"] += 1
                    elif "медленная работа" in question.lower():
                        problem_stats["Медленная работа программ"] += 1
                    elif "сбои" in question.lower() and "офисных" in question.lower():
                        problem_stats["Сбои в работе офисных приложений"] += 1
                    elif "печатью" in question.lower():
                        problem_stats["Проблемы с печатью"] += 1
                    elif "сетевыми дисками" in question.lower():
                        problem_stats["Сложности с сетевыми дисками"] += 1
                    else:
                        problem_stats[problem_text] += 1
            
            # Общая удовлетворенность
            elif "общая удовлетворенность" in question.lower():
                if answer:
                    try:
                        if isinstance(answer, str):
                            # Извлекаем число из строки
                            match = re.search(r'(\d+)', answer)
                            if match:
                                score = int(match.group(1))
                                satisfaction_stats[score] += 1
                            elif answer.strip().isdigit():
                                score = int(answer.strip())
                                satisfaction_stats[score] += 1
                        else:
                            score = int(answer)
                            satisfaction_stats[score] += 1
                    except:
                        pass
    
    print(f"Найдено локаций: {len(location_stats)}")
    print(f"Найдено вопросов: {len(question_stats)}")
    print(f"Найдено проблем: {len(problem_stats)}")
    print(f"Найдено оценок удовлетворенности: {len(satisfaction_stats)}")
    
    return {
        'locations': location_stats,
        'questions': question_stats,
        'problems': problem_stats,
        'satisfaction': satisfaction_stats,
        'total_respondents': total_respondents
    }

def save_parsed_data(parsed_data):
    """Сохраняет распарсенные данные в базу"""
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    try:
        # Очищаем старые данные
        cursor.execute("DELETE FROM locations")
        cursor.execute("DELETE FROM question_responses")
        cursor.execute("DELETE FROM problem_responses")
        cursor.execute("DELETE FROM satisfaction_scores")
        conn.commit()
        
        # Сохраняем локации
        for location, count in parsed_data['locations'].items():
            if location:  # Пропускаем пустые локации
                cursor.execute('''
                    INSERT INTO locations (location_name, response_count)
                    VALUES (?, ?)
                ''', (location, count))
        
        # Сохраняем вопросы и ответы
        for question, answers in parsed_data['questions'].items():
            for answer, count in answers.items():
                if answer:  # Пропускаем пустые ответы
                    cursor.execute('''
                        INSERT INTO question_responses (question_text, answer_text, count)
                        VALUES (?, ?, ?)
                    ''', (question, answer, count))
        
        # Сохраняем проблемы
        for problem, count in parsed_data['problems'].items():
            if problem:  # Пропускаем пустые проблемы
                cursor.execute('''
                    INSERT INTO problem_responses (problem_type, count)
                    VALUES (?, ?)
                ''', (problem, count))
        
        # Сохраняем оценки удовлетворенности
        for score, count in parsed_data['satisfaction'].items():
            if score > 0:  # Пропускаем нулевые оценки
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

# Маршруты
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Общее количество ответов по локациям
        cursor.execute("SELECT SUM(response_count) FROM locations")
        total_responses_row = cursor.fetchone()
        total_responses = total_responses_row[0] if total_responses_row and total_responses_row[0] else 0
        
        # Статистика по локациям
        cursor.execute('''
            SELECT location_name, response_count 
            FROM locations 
            WHERE response_count > 0
            ORDER BY response_count DESC
        ''')
        
        locations = []
        for row in cursor.fetchall():
            percent = (row['response_count'] / total_responses * 100) if total_responses > 0 else 0
            locations.append({
                'name': row['location_name'],
                'count': row['response_count'],
                'percent': round(percent, 1)
            })
        
        # Вопросы
        cursor.execute('''
            SELECT question_text, answer_text, count
            FROM question_responses 
            ORDER BY question_text, count DESC
        ''')
        
        questions_by_category = defaultdict(list)
        question_totals = defaultdict(int)
        
        for row in cursor.fetchall():
            questions_by_category[row['question_text']].append({
                'text': row['answer_text'],
                'count': row['count']
            })
            question_totals[row['question_text']] += row['count']
        
        questions_sections = []
        for question_text, answers in questions_by_category.items():
            total = question_totals[question_text]
            
            # Добавляем проценты
            for answer in answers:
                answer['percent'] = round((answer['count'] / total * 100), 1) if total > 0 else 0
            
            questions_sections.append({
                'title': question_text,
                'subtitle': '',
                'total': total,
                'answers': answers
            })
        
        # Проблемы
        cursor.execute('''
            SELECT problem_type, count
            FROM problem_responses 
            ORDER BY count DESC
        ''')
        
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
        cursor.execute('''
            SELECT score, count
            FROM satisfaction_scores 
            ORDER BY score
        ''')
        
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
            
            # Парсим данные
            parsed_data = parse_custom_json_data(json_data)
            
            # Сохраняем в базу
            success, error = save_parsed_data(parsed_data)
            
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

@app.route('/locations')
def locations():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT location_name, response_count 
        FROM locations 
        ORDER BY response_count DESC
    ''')
    
    locations = cursor.fetchall()
    conn.close()
    
    return render_template('simple_locations.html', locations=locations)

@app.route('/questions')
def questions():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT question_text, answer_text, count
        FROM question_responses 
        ORDER BY question_text, count DESC
    ''')
    
    questions_data = cursor.fetchall()
    conn.close()
    
    return render_template('simple_questions.html', questions=questions_data)

if __name__ == '__main__':
    init_database()
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
