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

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/www/survey-report/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_database():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT,
            response_count INTEGER,
            avg_satisfaction REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_key TEXT,
            question_type TEXT,
            avg_score REAL,
            response_count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT UNIQUE,
            description TEXT
        )
    ''')
    
    # Таблица для детальных ответов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detailed_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            location TEXT,
            question_key TEXT,
            answer_value INTEGER,
            answer_text TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    conn.row_factory = sqlite3.Row
    return conn

def extract_score(answer_text):
    if isinstance(answer_text, str):
        match = re.search(r'^(\d+)', answer_text.strip())
        if match:
            return int(match.group(1))
        
        text_lower = answer_text.lower()
        if 'плохо' in text_lower or 'неудобно' in text_lower:
            return 1
        elif 'приемлемо' in text_lower or 'удовлетворительно' in text_lower:
            return 2
        elif 'хорошо' in text_lower or 'удобно' in text_lower:
            return 3
        elif 'отлично' in text_lower:
            return 4
    
    return None

def parse_json_survey_data(json_data):
    responses = []
    
    for respondent_id, respondent_data in enumerate(json_data):
        response = {'respondent_id': respondent_id}
        for question_answer in respondent_data:
            if len(question_answer) >= 2:
                question = question_answer[0]
                answer = question_answer[1]
                
                if not isinstance(question, str):
                    continue
                
                question_lower = question.lower()
                
                if "локация" in question_lower or "вашу локацию" in question_lower:
                    response['location'] = str(answer).strip()
                elif "скорость загрузки" in question_lower or "быстроту запуска" in question_lower:
                    response['speed_score'] = extract_score(answer)
                    response['speed_text'] = answer
                elif "стабильность работы" in question_lower or "отсутствие зависаний" in question_lower:
                    response['stability_score'] = extract_score(answer)
                    response['stability_text'] = answer
                elif "удобство использования монитора" in question_lower or "контрастный, светлый" in question_lower:
                    response['monitor_score'] = extract_score(answer)
                    response['monitor_text'] = answer
                elif "яндекс" in question_lower:
                    response['yandex_score'] = extract_score(answer)
                    response['yandex_text'] = answer
                elif "ms office" in question_lower or "офис" in question_lower and "приложений" not in question_lower:
                    response['office_score'] = extract_score(answer)
                    response['office_text'] = answer
                elif "1с" in question_lower:
                    response['1c_score'] = extract_score(answer)
                    response['1c_text'] = answer
                elif "bitrix24" in question_lower:
                    response['bitrix_score'] = extract_score(answer)
                    response['bitrix_text'] = answer
                elif "обновлений" in question_lower:
                    response['updates_score'] = extract_score(answer)
                    response['updates_text'] = answer
                elif "общая удовлетворенность" in question_lower:
                    if isinstance(answer, (int, str)):
                        try:
                            if isinstance(answer, str):
                                match = re.search(r'(\d+)', answer)
                                if match:
                                    response['overall_satisfaction'] = int(match.group(1))
                                elif answer.strip().isdigit():
                                    response['overall_satisfaction'] = int(answer.strip())
                            else:
                                response['overall_satisfaction'] = int(answer)
                        except:
                            pass
        
        responses.append(response)
    
    return responses

def import_json_data(db_path, json_data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        init_database()
        
        cursor.execute("DELETE FROM survey_responses")
        cursor.execute("DELETE FROM question_stats")
        cursor.execute("DELETE FROM detailed_responses")
        conn.commit()
        
        responses = parse_json_survey_data(json_data)
        
        # Собираем статистику по локациям
        location_stats = {}
        question_stats = {}
        
        for response in responses:
            location = response.get('location', 'Не указана')
            if location == '':
                location = 'Не указана'
            
            if location not in location_stats:
                location_stats[location] = {'count': 0, 'total_satisfaction': 0}
            
            location_stats[location]['count'] += 1
            
            satisfaction = response.get('overall_satisfaction')
            if satisfaction:
                location_stats[location]['total_satisfaction'] += satisfaction
            
            # Сохраняем детальные ответы
            for key, value in response.items():
                if key.endswith('_score') and value is not None:
                    # Статистика по вопросам
                    question_key = key.replace('_score', '')
                    if question_key not in question_stats:
                        question_stats[question_key] = {'total': 0, 'count': 0, 'answers': {}}
                    
                    question_stats[question_key]['total'] += value
                    question_stats[question_key]['count'] += 1
                    
                    # Сохраняем текстовый ответ
                    text_key = key.replace('_score', '_text')
                    answer_text = response.get(text_key, str(value))
                    if answer_text not in question_stats[question_key]['answers']:
                        question_stats[question_key]['answers'][answer_text] = 0
                    question_stats[question_key]['answers'][answer_text] += 1
        
        # Сохраняем статистику по локациям
        for location, stats in location_stats.items():
            avg_satisfaction = 0
            if stats['count'] > 0 and stats['total_satisfaction'] > 0:
                avg_satisfaction = stats['total_satisfaction'] / stats['count']
            
            cursor.execute('''
                INSERT INTO survey_responses (location_name, response_count, avg_satisfaction)
                VALUES (?, ?, ?)
            ''', (location, stats['count'], avg_satisfaction))
        
        # Сохраняем статистику по вопросам
        for question_key, stats in question_stats.items():
            avg_score = 0
            if stats['count'] > 0:
                avg_score = stats['total'] / stats['count']
            
            cursor.execute('''
                INSERT INTO question_stats (question_key, question_type, avg_score, response_count)
                VALUES (?, ?, ?, ?)
            ''', (question_key, 'score', avg_score, stats['count']))
        
        conn.commit()
        return len(responses), None
        
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
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT SUM(response_count) FROM survey_responses")
        total_row = cursor.fetchone()
        total_responses = total_row[0] if total_row and total_row[0] else 0
        
        cursor.execute('''
            SELECT location_name, response_count 
            FROM survey_responses 
            WHERE response_count > 0
            ORDER BY response_count DESC
        ''')
        
        locations = []
        for row in cursor.fetchall():
            if row['response_count'] > 0:
                percent = (row['response_count'] / total_responses * 100) if total_responses > 0 else 0
                locations.append({
                    'name': row['location_name'],
                    'count': row['response_count'],
                    'percent': round(percent, 1)
                })
        
        # Получаем данные для вопросов
        questions_data = []
        cursor.execute("SELECT * FROM question_stats")
        for q in cursor.fetchall():
            questions_data.append({
                'key': q['question_key'],
                'avg_score': q['avg_score'],
                'count': q['response_count']
            })
        
        # Примерные вопросы (можно доработать для реальных данных)
        questions = [
            {
                'title': 'Оцените скорость загрузки системы',
                'subtitle': 'Оцените быстроту запуска ПК и программ',
                'total': total_responses,
                'answers': [
                    {'text': '3 - Хорошо', 'count': int(total_responses * 0.387), 'percent': 38.7},
                    {'text': '2 - Приемлемо', 'count': int(total_responses * 0.508), 'percent': 50.8},
                    {'text': '1 - Плохо', 'count': int(total_responses * 0.105), 'percent': 10.5}
                ]
            }
        ]
        
        return render_template('dashboard.html',
                             total_responses=total_responses,
                             location_stats={
                                 'total': total_responses,
                                 'locations': locations
                             },
                             questions=questions,
                             update_time=datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))
                             
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html',
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
            
            db_path = '/var/www/survey-report/survey_complete.db'
            count, error = import_json_data(db_path, json_data)
            
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

@app.route('/import_locations', methods=['POST'])
def import_locations():
    if 'locations_file' not in request.files:
        return render_template('import_simple.html', 
                             message='Файл не выбран',
                             message_type='error')
    
    file = request.files['locations_file']
    if file.filename == '':
        return render_template('import_simple.html',
                             message='Файл не выбран',
                             message_type='error')
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            df = pd.read_excel(file)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM locations')
            
            for _, row in df.iterrows():
                location_name = row.iloc[0] if len(row) > 0 else ''
                description = row.iloc[1] if len(row) > 1 else ''
                
                cursor.execute('''
                    INSERT INTO locations (location_name, description)
                    VALUES (?, ?)
                ''', (str(location_name), str(description)))
            
            conn.commit()
            conn.close()
            
            return render_template('import_simple.html',
                                 message=f'Успешно импортировано {len(df)} локаций',
                                 message_type='success')
        
        except Exception as e:
            return render_template('import_simple.html',
                                 message=f'Ошибка импорта: {str(e)}',
                                 message_type='error',
                                 details=traceback.format_exc())
    
    return render_template('import_simple.html',
                         message='Неверный формат файла',
                         message_type='error')

@app.route('/locations')
def locations():
    conn = get_db_connection()
    
    try:
        locations_data = conn.execute('''
            SELECT location_name, response_count, avg_satisfaction
            FROM survey_responses
            ORDER BY response_count DESC
        ''').fetchall()
        
        all_locations = conn.execute('SELECT location_name FROM locations').fetchall()
        
        return render_template('locations.html', 
                             locations=locations_data,
                             all_locations=all_locations)
    except Exception as e:
        print(f"Locations error: {e}")
        return f"Ошибка: {e}"
    finally:
        conn.close()

@app.route('/questions')
def questions():
    conn = get_db_connection()
    
    try:
        questions_data = conn.execute('''
            SELECT question_key, question_type, avg_score, response_count
            FROM question_stats
            ORDER BY question_key
        ''').fetchall()
        
        readable_questions = []
        question_names = {
            'speed': 'Скорость загрузки системы',
            'stability': 'Стабильность работы',
            'monitor': 'Удобство монитора',
            'yandex': 'Приложения Яндекс',
            'office': 'MS Office',
            '1c': '1С',
            'bitrix': 'Bitrix24',
            'thirdparty': 'Сторонние приложения',
            'updates': 'Обновления ПО'
        }
        
        for q in questions_data:
            readable_name = question_names.get(q['question_key'], q['question_key'])
            readable_questions.append({
                'name': readable_name,
                'type': q['question_type'],
                'avg_score': q['avg_score'],
                'count': q['response_count']
            })
        
        return render_template('questions.html', questions=readable_questions)
    except Exception as e:
        print(f"Questions error: {e}")
        return f"Ошибка: {e}"
    finally:
        conn.close()

if __name__ == '__main__':
    init_database()
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
