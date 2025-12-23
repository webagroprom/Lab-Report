#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import pandas as pd
import os
import json
from werkzeug.utils import secure_filename
import traceback
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/www/survey-report/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Создаем папку для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_score(answer_text):
    """
    Извлекает числовую оценку из текста ответа
    """
    if isinstance(answer_text, str):
        # Пытаемся извлечь число из начала строки
        match = re.search(r'^(\d+)', answer_text.strip())
        if match:
            return int(match.group(1))
        
        # Пробуем извлечь по ключевым словам
        if 'плохо' in answer_text.lower() or 'неудобно' in answer_text.lower():
            return 1
        elif 'приемлемо' in answer_text.lower() or 'удовлетворительно' in answer_text.lower():
            return 2
        elif 'хорошо' in answer_text.lower() or 'удобно' in answer_text.lower():
            return 3
        elif 'отлично' in answer_text.lower():
            return 4
    
    # Если не смогли извлечь, возвращаем None
    return None

def parse_json_survey_data(json_data):
    """
    Парсит данные опроса из JSON формата
    Возвращает список словарей с ответами
    """
    responses = []
    
    for respondent_data in json_data:
        response = {}
        for question_answer in respondent_data:
            if len(question_answer) >= 2:
                question = question_answer[0]
                answer = question_answer[1]
                
                # Проверяем что question - строка
                if not isinstance(question, str):
                    continue
                    
                # Определяем тип вопроса по содержанию
                if "локация" in question.lower():
                    response['location'] = answer
                elif "скорость загрузки" in question.lower() or "быстроту запуска" in question.lower():
                    response['speed_score'] = extract_score(answer)
                elif "стабильность работы" in question.lower() or "отсутствие зависаний" in question.lower():
                    response['stability_score'] = extract_score(answer)
                elif "удобство использования монитора" in question.lower() or "контрастный, светлый" in question.lower():
                    response['monitor_score'] = extract_score(answer)
                elif "зависание компьютера" in question.lower() and answer:
                    response['freeze_problem'] = True
                elif "медленная работа программ" in question.lower() and answer:
                    response['slow_problem'] = True
                elif "сбои в работе офисных приложений" in question.lower() and answer:
                    response['office_problem'] = True
                elif "проблемы с печатью" in question.lower() and answer:
                    response['print_problem'] = True
                elif "сложности с сетевыми дисками" in question.lower() and answer:
                    response['network_problem'] = True
                elif "яндекс" in question.lower():
                    response['yandex_score'] = extract_score(answer)
                elif "ms office" in question.lower() or "офис" in question.lower() and "приложений" not in question.lower():
                    response['office_score'] = extract_score(answer)
                elif "1с" in question.lower():
                    response['1c_score'] = extract_score(answer)
                elif "bitrix24" in question.lower():
                    response['bitrix_score'] = extract_score(answer)
                elif "сторонних приложений" in question.lower():
                    response['thirdparty_score'] = extract_score(answer)
                elif "обновлений по" in question.lower() or "обновлений ос" in question.lower():
                    response['updates_score'] = extract_score(answer)
                elif "общая удовлетворенность рабочего места" in question.lower() and isinstance(answer, (int, str)):
                    try:
                        if isinstance(answer, str):
                            # Пробуем извлечь число из строки
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
    """
    Импортирует данные из JSON в базу данных
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Очищаем старые данные
        cursor.execute("DELETE FROM survey_responses")
        cursor.execute("DELETE FROM question_stats")
        conn.commit()
        
        # Парсим данные
        responses = parse_json_survey_data(json_data)
        
        # Собираем статистику по локациям
        location_stats = {}
        question_stats = {}
        
        for response in responses:
            location = response.get('location', 'Не указана')
            
            # Добавляем локацию в статистику
            if location not in location_stats:
                location_stats[location] = {
                    'count': 0,
                    'total_satisfaction': 0
                }
            
            location_stats[location]['count'] += 1
            
            # Суммируем общую удовлетворенность
            satisfaction = response.get('overall_satisfaction')
            if satisfaction:
                location_stats[location]['total_satisfaction'] += satisfaction
            
            # Собираем статистику по оценкам
            for key, value in response.items():
                if key.endswith('_score') and value is not None:
                    if key not in question_stats:
                        question_stats[key] = {'total': 0, 'count': 0}
                    
                    question_stats[key]['total'] += value
                    question_stats[key]['count'] += 1
        
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
        for question, stats in question_stats.items():
            avg_score = 0
            if stats['count'] > 0:
                avg_score = stats['total'] / stats['count']
            
            # Определяем тип вопроса
            question_type = 'score'
            
            cursor.execute('''
                INSERT INTO question_stats (question_key, question_type, avg_score, response_count)
                VALUES (?, ?, ?, ?)
            ''', (question, question_type, avg_score, stats['count']))
        
        conn.commit()
        return len(responses), None
        
    except Exception as e:
        conn.rollback()
        return 0, str(e) + "\n" + traceback.format_exc()
    
    finally:
        conn.close()

def get_db_connection():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect(url_for('import_page'))

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
            # Читаем JSON файл
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Импортируем данные
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
            # Читаем Excel файл
            df = pd.read_excel(file)
            
            conn = get_db_connection()
            
            # Очищаем старые данные о локациях
            conn.execute('DELETE FROM locations')
            
            # Импортируем новые данные
            for _, row in df.iterrows():
                location_name = row.iloc[0] if len(row) > 0 else ''
                description = row.iloc[1] if len(row) > 1 else ''
                
                conn.execute('''
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
    
    # Получаем статистику по локациям
    locations_data = conn.execute('''
        SELECT location_name, response_count, avg_satisfaction
        FROM survey_responses
        ORDER BY response_count DESC
    ''').fetchall()
    
    # Получаем список всех локаций
    all_locations = conn.execute('SELECT location_name FROM locations').fetchall()
    
    conn.close()
    
    return render_template('locations.html', 
                         locations=locations_data,
                         all_locations=all_locations)

@app.route('/questions')
def questions():
    conn = get_db_connection()
    
    # Получаем статистику по вопросам
    questions_data = conn.execute('''
        SELECT question_key, question_type, avg_score, response_count
        FROM question_stats
        ORDER BY question_key
    ''').fetchall()
    
    # Преобразуем ключи вопросов в читаемые названия
    readable_questions = []
    question_names = {
        'speed_score': 'Скорость загрузки системы',
        'stability_score': 'Стабильность работы',
        'monitor_score': 'Удобство монитора',
        'yandex_score': 'Приложения Яндекс',
        'office_score': 'MS Office',
        '1c_score': '1С',
        'bitrix_score': 'Bitrix24',
        'thirdparty_score': 'Сторонние приложения',
        'updates_score': 'Обновления ПО'
    }
    
    for q in questions_data:
        readable_name = question_names.get(q['question_key'], q['question_key'])
        readable_questions.append({
            'name': readable_name,
            'type': q['question_type'],
            'avg_score': q['avg_score'],
            'count': q['response_count']
        })
    
    conn.close()
    
    return render_template('questions.html', questions=readable_questions)

if __name__ == '__main__':
    # Создаем базу данных, если её нет
    if not os.path.exists('/var/www/survey-report/survey_complete.db'):
        conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
        cursor = conn.cursor()
        
        # Таблица для ответов опроса
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS survey_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT,
                response_count INTEGER,
                avg_satisfaction REAL
            )
        ''')
        
        # Таблица для статистики по вопросам
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_key TEXT,
                question_type TEXT,
                avg_score REAL,
                response_count INTEGER
            )
        ''')
        
        # Таблица для локаций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT UNIQUE,
                description TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("База данных создана успешно")
    
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
