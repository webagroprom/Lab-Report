#!/usr/bin/env python3
import sqlite3
import os

def init_database():
    db_path = '/var/www/survey-report/survey_complete.db'
    
    # Удаляем старую базу если существует
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
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
    
    # Вставляем тестовые данные
    cursor.execute('''
        INSERT INTO survey_responses (location_name, response_count, avg_satisfaction)
        VALUES ('Московский офис', 10, 7.5),
               ('Завод Тосно', 5, 6.2)
    ''')
    
    cursor.execute('''
        INSERT INTO question_stats (question_key, question_type, avg_score, response_count)
        VALUES ('speed_score', 'score', 2.5, 15),
               ('stability_score', 'score', 2.8, 15)
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"База данных создана: {db_path}")
    print("Таблицы: survey_responses, question_stats, locations")

if __name__ == "__main__":
    init_database()
