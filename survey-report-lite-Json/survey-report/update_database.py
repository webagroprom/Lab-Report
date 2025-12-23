#!/usr/bin/env python3
import sqlite3
import json
import re

def update_database_schema():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    # Создаем таблицу для детальной статистики ответов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_key TEXT,
            answer_text TEXT,
            answer_value INTEGER,
            count INTEGER
        )
    ''')
    
    # Создаем таблицу для статистики по локациям с деталями
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT,
            response_count INTEGER,
            satisfaction_distribution TEXT  -- JSON с распределением оценок
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Схема базы данных обновлена")

def parse_detailed_stats(json_data):
    """Парсит детальную статистику из JSON"""
    stats = {
        'locations': {},
        'questions': {}
    }
    
    question_patterns = {
        'location': 'локация',
        'speed': 'скорость загрузки',
        'stability': 'стабильность работы',
        'monitor': 'удобство использования монитора',
        'problems': 'с какими проблемами',
        'yandex': 'яндекс',
        'office': 'ms office',
        '1c': '1с',
        'bitrix': 'bitrix24',
        'thirdparty': 'сторонних приложений',
        'updates': 'обновлений',
        'overall': 'общая удовлетворенность'
    }
    
    for respondent_data in json_data:
        for question_answer in respondent_data:
            if len(question_answer) >= 2:
                question = question_answer[0]
                answer = question_answer[1]
                
                if not isinstance(question, str):
                    continue
                
                # Определяем тип вопроса
                for key, pattern in question_patterns.items():
                    if pattern in question.lower():
                        if key == 'location':
                            loc = answer
                            if loc not in stats['locations']:
                                stats['locations'][loc] = 0
                            stats['locations'][loc] += 1
                        else:
                            if key not in stats['questions']:
                                stats['questions'][key] = {}
                            
                            # Извлекаем значение ответа
                            if isinstance(answer, str):
                                # Пробуем извлечь числовое значение
                                match = re.search(r'(\d+)\s*-\s*([\w\s]+)', answer)
                                if match:
                                    answer_val = match.group(1)
                                    answer_text = match.group(2)
                                else:
                                    answer_val = '1' if 'плохо' in answer.lower() else \
                                                '2' if 'приемлемо' in answer.lower() or 'удовлетворительно' in answer.lower() else \
                                                '3' if 'хорошо' in answer.lower() or 'удобно' in answer.lower() else answer
                                    answer_text = answer
                            else:
                                answer_val = str(answer)
                                answer_text = str(answer)
                            
                            answer_key = f"{answer_val} - {answer_text}"
                            if answer_key not in stats['questions'][key]:
                                stats['questions'][key][answer_key] = 0
                            stats['questions'][key][answer_key] += 1
                        break
    
    return stats

if __name__ == "__main__":
    update_database_schema()
