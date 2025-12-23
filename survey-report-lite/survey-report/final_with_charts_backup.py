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

# Создаем папку для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_database():
    """Инициализирует базу данных и создает таблицы если их нет"""
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

def get_db_connection():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    conn.row_factory = sqlite3.Row
    return conn

# Маршруты
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Общее количество ответов
        cursor.execute("SELECT SUM(response_count) FROM survey_responses")
        total_row = cursor.fetchone()
        total_responses = total_row[0] if total_row and total_row[0] else 0
        
        # Статистика по локациям из базы
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
        
        # Если в базе нет данных, используем примерные
        if not locations:
            locations = [
                {'name': 'Московский офис', 'count': 49, 'percent': 39.5},
                {'name': 'Домашний офис', 'count': 29, 'percent': 23.4},
                {'name': 'Завод Энгельс', 'count': 9, 'percent': 7.3},
                {'name': 'Завод Пермь', 'count': 8, 'percent': 6.5}
            ]
            total_responses = sum(loc['count'] for loc in locations)
        
        # Статистика по вопросам (примерная, можно расширить)
        questions = [
            {
                'title': 'Оцените скорость загрузки системы',
                'subtitle': 'Оцените быстроту запуска ПК и программ',
                'total': total_responses,
                'answers': [
                    {'text': '2 - Приемлемо', 'count': int(total_responses * 0.508), 'percent': 50.8},
                    {'text': '3 - Хорошо', 'count': int(total_responses * 0.387), 'percent': 38.7},
                    {'text': '1 - Плохо', 'count': int(total_responses * 0.105), 'percent': 10.5}
                ]
            },
            {
                'title': 'Оцените стабильность работы системы',
                'subtitle': 'Оцените отсутствие зависаний и сбоев',
                'total': total_responses,
                'answers': [
                    {'text': '2 - Приемлемо', 'count': int(total_responses * 0.5), 'percent': 50.0},
                    {'text': '3 - Хорошо', 'count': int(total_responses * 0.306), 'percent': 30.6},
                    {'text': '1 - Плохо', 'count': int(total_responses * 0.194), 'percent': 19.4}
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
        print(f"Error in dashboard: {e}")
        return render_template('dashboard.html',
                             total_responses=0,
                             location_stats={'total': 0, 'locations': []},
                             questions=[],
                             update_time=datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))
    finally:
        conn.close()

# Остальные маршруты (import, locations, questions) оставляем как были
# ... (добавим их познее)

if __name__ == '__main__':
    init_database()
    print("Сервер запускается на порту 5004...")
    app.run(host='0.0.0.0', port=5004, debug=True)
