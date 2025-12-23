#!/usr/bin/env python3
import json
import sqlite3
import os
from datetime import datetime
import traceback

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
                question = question_answer[0].strip()
                answer = question_answer[1]
                
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
                elif "ms office" in question.lower() or "офис" in question.lower():
                    response['office_score'] = extract_score(answer)
                elif "1с" in question.lower():
                    response['1c_score'] = extract_score(answer)
                elif "bitrix24" in question.lower():
                    response['bitrix_score'] = extract_score(answer)
                elif "сторонних приложений" in question.lower():
                    response['thirdparty_score'] = extract_score(answer)
                elif "обновлений по" in question.lower() or "обновлений ос" in question.lower():
                    response['updates_score'] = extract_score(answer)
                elif "общая удовлетворенность рабочего места" in question.lower() and answer.isdigit():
                    response['overall_satisfaction'] = int(answer)
                elif "ваши предложения" in question.lower() and answer:
                    response['suggestions'] = answer
        
        responses.append(response)
    
    return responses

def extract_score(answer_text):
    """
    Извлекает числовую оценку из текста ответа
    """
    if isinstance(answer_text, str):
        # Пытаемся извлечь число из начала строки
        import re
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
                    'total_satisfaction': 0,
                    'scores': {}
                }
            
            location_stats[location]['count'] += 1
            
            # Суммируем общую удовлетворенность
            satisfaction = response.get('overall_satisfaction')
            if satisfaction:
                location_stats[location]['total_satisfaction'] += satisfaction
            
            # Собираем статистику по оценкам
            for key, value in response.items():
                if key.endswith('_score') and value is not None:
                    question_key = key.replace('_score', '')
                    if question_key not in question_stats:
                        question_stats[question_key] = {'total': 0, 'count': 0}
                    
                    question_stats[question_key]['total'] += value
                    question_stats[question_key]['count'] += 1
        
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
            if question in ['freeze', 'slow', 'office', 'print', 'network']:
                question_type = 'problem'
            
            cursor.execute('''
                INSERT INTO question_stats (question_key, question_type, avg_score, response_count)
                VALUES (?, ?, ?, ?)
            ''', (question, question_type, avg_score, stats['count']))
        
        conn.commit()
        return len(responses), None
        
    except Exception as e:
        conn.rollback()
        return 0, str(e)
    
    finally:
        conn.close()

def main():
    """
    Основная функция для тестирования импорта
    """
    db_path = '/var/www/survey-report/survey_complete.db'
    
    # Пример использования
    test_json = [
        [
            ["Укажите вашу локацию", "Московский офис"],
            ["Оцените скорость загрузки системы", "2 - Приемлемо"],
            ["Оцените стабильность работы системы", "3 - Хорошо"],
            ["Общая удовлетворенность рабочего места", "8"]
        ]
    ]
    
    count, error = import_json_data(db_path, test_json)
    if error:
        print(f"Ошибка: {error}")
    else:
        print(f"Успешно импортировано {count} ответов")

if __name__ == "__main__":
    main()
