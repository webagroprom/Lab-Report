#!/usr/bin/env python3
import sqlite3
import json

def check_database():
    db_path = '/var/www/survey-report/survey_complete.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== Проверка таблиц ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Таблицы в базе:", tables)
    
    print("\n=== Данные в survey_responses ===")
    cursor.execute("SELECT * FROM survey_responses")
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("Нет данных в survey_responses")
    
    print("\n=== Данные в question_stats ===")
    cursor.execute("SELECT * FROM question_stats")
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("Нет данных в question_stats")
    
    conn.close()

if __name__ == "__main__":
    check_database()
