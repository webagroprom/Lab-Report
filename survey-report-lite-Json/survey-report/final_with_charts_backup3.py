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
from collections import defaultdict

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/www/survey-report/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_database():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            location TEXT,
            question_key TEXT,
            answer_value INTEGER,
            answer_text TEXT,
            question_text TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT UNIQUE,
            response_count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_answer_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT,
            answer_text TEXT,
            answer_value INTEGER,
            count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS overall_satisfaction (
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

def extract_score_and_text(answer):
    """Извлекает числовую оценку и текст из ответа"""
    if isinstance(answer, str):
        # Пробуем найти паттерн "1 - Плохо", "2 - Приемлемо" и т.д.
        match = re.search(r'^(\d+)\s*[-–]\s*(.+)', answer.strip())
        if match:
            return int(match.group(1)), match.group(2).strip()
        
        # Пробуем найти просто число
        match_num = re.search(r'^(\d+)', answer.strip())
        if match_num:
            value = int(match_num.group(1))
            text = answer.strip()
            return value, text
        
        # Определяем по ключевым словам
        text_lower = answer.lower()
        if 'плохо' in text_lower or 'неудобно' in text_lower:
            return 1, answer.strip()
        elif 'приемлемо' in text_lower:
            return 2, answer.strip()
        elif 'удовлетворительно' in text_lower:
            return 2, answer.strip()  # Удовлетворительно = 2
        elif 'хорошо' in text_lower or 'удобно' in text_lower:
            return 3, answer.strip()
        elif 'отлично' in text_lower:
            return 4, answer.strip()
    
    # Если ответ - число
    if isinstance(answer, (int, float)):
        return int(answer), str(answer)
    
    return None, str(answer) if answer else ""

def parse_and_store_json_data(json_data):
    """Парсит и сохраняет данные из JSON"""
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    try:
        # Очищаем старые данные
        cursor.execute("DELETE FROM survey_data")
        cursor.execute("DELETE FROM location_stats")
        cursor.execute("DELETE FROM question_answer_stats")
        cursor.execute("DELETE FROM overall_satisfaction")
        conn.commit()
        
        # Словари для статистики
        location_counts = defaultdict(int)
        question_stats = defaultdict(lambda: defaultdict(int))
        satisfaction_counts = defaultdict(int)
        
        for respondent_id, respondent_data in enumerate(json_data):
            current_location = "Не указана"
            
            for question_answer in respondent_data:
                if len(question_answer) >= 2:
                    question = question_answer[0]
                    answer = question_answer[1]
                    
                    if not isinstance(question, str):
                        continue
                    
                    # Определяем тип вопроса
                    question_lower = question.lower()
                    question_key = ""
                    
                    if "локация" in question_lower or "вашу локацию" in question_lower:
                        current_location = str(answer).strip() if answer else "Не указана"
                        location_counts[current_location] += 1
                        continue
                    
                    elif "скорость загрузки" in question_lower or "быстроту запуска" in question_lower:
                        question_key = "speed"
                    elif "стабильность работы" in question_lower or "отсутствие зависаний" in question_lower:
                        question_key = "stability"
                    elif "удобство использования монитора" in question_lower or "контрастный, светлый" in question_lower:
                        question_key = "monitor"
                    elif "яндекс" in question_lower:
                        question_key = "yandex"
                    elif "ms office" in question_lower or "офис" in question_lower:
                        question_key = "office"
                    elif "1с" in question_lower:
                        question_key = "1c"
                    elif "bitrix24" in question_lower:
                        question_key = "bitrix"
                    elif "сторонних приложений" in question_lower:
                        question_key = "thirdparty"
                    elif "обновлений" in question_lower:
                        question_key = "updates"
                    elif "общая удовлетворенность" in question_lower:
                        question_key = "overall"
                    elif "проблемы" in question_lower or "с какими проблемами" in question_lower:
                        if answer:  # Если есть ответ на проблему
                            problem_type = ""
                            if "зависание компьютера" in question_lower:
                                problem_type = "freeze"
                            elif "медленная работа программ" in question_lower:
                                problem_type = "slow"
                            elif "сбои в работе офисных приложений" in question_lower:
                                problem_type = "office_problems"
                            elif "проблемы с печатью" in question_lower:
                                problem_type = "print"
                            elif "сложности с сетевыми дисками" in question_lower:
                                problem_type = "network"
                            
                            if problem_type and answer.strip():
                                question_stats[f"problem_{problem_type}"][answer] += 1
                        continue
                    else:
                        # Пропускаем вопросы без ключа
                        continue
                    
                    # Извлекаем оценку и текст
                    value, text = extract_score_and_text(answer)
                    
                    if question_key:
                        # Сохраняем в базу
                        cursor.execute('''
                            INSERT INTO survey_data (respondent_id, location, question_key, answer_value, answer_text, question_text)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (respondent_id, current_location, question_key, value, text, question[:100]))
                        
                        # Обновляем статистику
                        if value:
                            answer_key = f"{value} - {text}" if text else str(value)
                            question_stats[question_key][answer_key] += 1
                        
                        # Для общей удовлетворенности считаем отдельно
                        if question_key == "overall" and value:
                            satisfaction_counts[value] += 1
        
        # Сохраняем статистику локаций
        for location, count in location_counts.items():
            cursor.execute('''
                INSERT INTO location_stats (location_name, response_count)
                VALUES (?, ?)
            ''', (location, count))
        
        # Сохраняем статистику вопросов-ответов
        for question_key, answers in question_stats.items():
            for answer_text, count in answers.items():
                # Извлекаем значение из текста ответа
                value_match = re.search(r'^(\d+)', answer_text)
                value = int(value_match.group(1)) if value_match else None
                
                cursor.execute('''
                    INSERT INTO question_answer_stats (question_text, answer_text, answer_value, count)
                    VALUES (?, ?, ?, ?)
                ''', (question_key, answer_text, value, count))
        
        # Сохраняем статистику общей удовлетворенности
        for score, count in satisfaction_counts.items():
            cursor.execute('''
                INSERT INTO overall_satisfaction (score, count)
                VALUES (?, ?)
            ''', (score, count))
        
        conn.commit()
        return len(json_data), None
        
    except Exception as e:
        conn.rollback()
        return 0, str(e) + "\n" + traceback.format_exc()
    finally:
        conn.close()

# Маршруты
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    
    try:
        # Общее количество ответов из локаций
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(response_count) FROM location_stats")
        total_responses_row = cursor.fetchone()
        total_responses = total_responses_row[0] if total_responses_row and total_responses_row[0] else 0
        
        # Статистика по локациям
        cursor.execute('''
            SELECT location_name, response_count 
            FROM location_stats 
            WHERE response_count > 0 AND location_name != 'Не указана'
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
        
        # Получаем данные для вопросов
        questions_sections = []
        
        # Список вопросов в порядке отображения
        question_order = [
            ('speed', 'Оцените скорость загрузки системы', 'Оцените быстроту запуска ПК и программ'),
            ('stability', 'Оцените стабильность работы системы', 'Оцените отсутствие зависаний и сбоев'),
            ('monitor', 'Оцените удобство использования монитора', 'Достаточно ли контрастный, светлый, насыщенный'),
            ('yandex', 'Приложения семейства Яндекс', 'Удобство интерфейса, стабильность работы приложения'),
            ('office', 'Пакеты MS Office', 'Удобство интерфейса, стабильность работы приложения'),
            ('1c', 'Приложение 1С', 'Удобство интерфейса, стабильность работы приложения'),
            ('bitrix', 'Приложение Bitrix24', 'Удобство интерфейса, стабильность работы приложения'),
            ('thirdparty', 'Сторонние приложения', 'Удобство интерфейса, стабильность работы приложения'),
            ('updates', 'Обновления ПО и ОС', 'Кратко оцените работу обновлений')
        ]
        
        for q_key, q_title, q_subtitle in question_order:
            cursor.execute('''
                SELECT answer_text, SUM(count) as total_count
                FROM question_answer_stats 
                WHERE question_text = ?
                GROUP BY answer_text
                ORDER BY answer_value DESC
            ''', (q_key,))
            
            answers = []
            section_total = 0
            for row in cursor.fetchall():
                answers.append({
                    'text': row['answer_text'],
                    'count': row['total_count']
                })
                section_total += row['total_count']
            
            if answers:
                # Сортируем по count
                answers.sort(key=lambda x: x['count'], reverse=True)
                
                # Добавляем проценты
                for answer in answers:
                    answer['percent'] = round((answer['count'] / section_total * 100), 1) if section_total > 0 else 0
                
                questions_sections.append({
                    'title': q_title,
                    'subtitle': q_subtitle,
                    'total': section_total,
                    'answers': answers[:10]  # Берем топ 10 ответов
                })
        
        # Проблемы
        cursor.execute('''
            SELECT question_text, answer_text, SUM(count) as total_count
            FROM question_answer_stats 
            WHERE question_text LIKE 'problem_%'
            GROUP BY question_text, answer_text
            HAVING answer_text != '' AND answer_text IS NOT NULL
        ''')
        
        problems = defaultdict(int)
        total_problems = 0
        for row in cursor.fetchall():
            problems[row['answer_text']] += row['total_count']
            total_problems += row['total_count']
        
        problem_list = []
        for problem, count in sorted(problems.items(), key=lambda x: x[1], reverse=True):
            percent = round((count / total_problems * 100), 1) if total_problems > 0 else 0
            problem_list.append({
                'text': problem,
                'count': count,
                'percent': percent
            })
        
        if problem_list:
            questions_sections.append({
                'title': 'С какими проблемами вы сталкиваетесь чаще всего?',
                'subtitle': '',
                'total': total_problems,
                'answers': problem_list
            })
        
        # Общая удовлетворенность
        cursor.execute('''
            SELECT score, count 
            FROM overall_satisfaction 
            WHERE score IS NOT NULL
            ORDER BY score
        ''')
        
        satisfaction_data = []
        total_satisfaction = 0
        for row in cursor.fetchall():
            satisfaction_data.append({
                'text': str(row['score']),
                'count': row['count']
            })
            total_satisfaction += row['count']
        
        if satisfaction_data:
            for item in satisfaction_data:
                item['percent'] = round((item['count'] / total_satisfaction * 100), 1) if total_satisfaction > 0 else 0
            
            questions_sections.append({
                'title': 'Общая удовлетворенность рабочего места',
                'subtitle': '',
                'total': total_satisfaction,
                'answers': satisfaction_data
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

# Остальные маршруты остаются похожими, но с новой функцией импорта
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
            
            count, error = parse_and_store_json_data(json_data)
            
            if error:
                return render_template('import_simple.html',
                                     message=f'Ошибка импорта: {error}',
                                     message_type='error')
            else:
                return render_template('import_simple.html',
                                     message=f'Успешно импортировано {count} ответов из JSON файла',
                                     message_type='success')
        
        except Exception as e:
            return render_template('import_simple.html',
                                 message=f'Ошибка обработки файла: {str(e)}',
                                 message_type='error',
                                 details=traceback.format_exc())
    
    return render_template('import_simple.html',
                         message='Неверный формат файла. Требуется JSON',
                         message_type='error')

# Простые маршруты для locations и questions
@app.route('/locations')
def locations():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT location_name, response_count 
        FROM location_stats 
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
        SELECT question_text, answer_text, SUM(count) as total_count
        FROM question_answer_stats 
        GROUP BY question_text, answer_text
        ORDER BY question_text, total_count DESC
    ''')
    
    questions_data = cursor.fetchall()
    conn.close()
    
    return render_template('simple_questions.html', questions=questions_data)

if __name__ == '__main__':
    init_database()
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
