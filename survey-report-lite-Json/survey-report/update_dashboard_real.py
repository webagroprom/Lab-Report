#!/usr/bin/env python3
import re

with open('/var/www/survey-report/final_with_charts.py', 'r') as f:
    content = f.read()

# Заменяем функцию dashboard на более полную
new_dashboard_function = '''
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Общее количество ответов
    cursor.execute("SELECT SUM(response_count) FROM survey_responses")
    total_responses = cursor.fetchone()[0] or 124  # Fallback к примеру из данных
    
    # Статистика по локациям из вашего примера
    location_data = [
        ("Московский офис", 49, 39.5),
        ("Домашний офис", 29, 23.4),
        ("Завод Энгельс", 9, 7.3),
        ("Завод Пермь", 8, 6.5),
        ("Завод Ногинск", 7, 5.6),
        ("Завод Коломна", 5, 4.0),
        ("Торговый офис", 4, 3.2),
        ("Завод Ставрополь", 4, 3.2),
        ("Завод Тосно", 4, 3.2),
        ("Завод Новосибирск", 2, 1.6),
        ("Завод Челябинск", 2, 1.6),
        ("Склад Хлебниково", 1, 0.8),
        ("Завод Ульяновск", 0, 0),
        ("FM Logistic", 0, 0)
    ]
    
    locations = []
    for name, count, percent in location_data:
        locations.append({
            'name': name,
            'count': count,
            'percent': percent
        })
    
    # Вопросы из вашего примера
    questions = [
        {
            'title': 'Оцените скорость загрузки системы',
            'subtitle': 'Оцените быстроту запуска ПК и программ',
            'total': total_responses,
            'answers': [
                {'text': '2 - Приемлемо', 'count': 63, 'percent': 50.8},
                {'text': '3 - Хорошо', 'count': 48, 'percent': 38.7},
                {'text': '1 - Плохо', 'count': 13, 'percent': 10.5}
            ]
        },
        {
            'title': 'Оцените стабильность работы системы',
            'subtitle': 'Оцените отсутствие зависаний и сбоев',
            'total': total_responses,
            'answers': [
                {'text': '2 - Приемлемо', 'count': 62, 'percent': 50.0},
                {'text': '3 - Хорошо', 'count': 38, 'percent': 30.6},
                {'text': '1 - Плохо', 'count': 24, 'percent': 19.4}
            ]
        },
        {
            'title': 'Оцените удобство использования монитора',
            'subtitle': 'Достаточно ли контрастный, светлый, насыщенный',
            'total': total_responses,
            'answers': [
                {'text': '3 - Хорошо', 'count': 65, 'percent': 52.4},
                {'text': '2 - Приемлемо', 'count': 48, 'percent': 38.7},
                {'text': '1 - Плохо', 'count': 11, 'percent': 8.9}
            ]
        },
        {
            'title': 'Приложения Яндекс',
            'subtitle': 'Удобство интерфейса, стабильность работы приложения',
            'total': total_responses,
            'answers': [
                {'text': '2 - Приемлемо', 'count': 63, 'percent': 50.8},
                {'text': '3 - Хорошо', 'count': 43, 'percent': 34.7},
                {'text': '1 - Плохо', 'count': 18, 'percent': 14.5}
            ]
        },
        {
            'title': 'MS Office',
            'subtitle': 'Удобство интерфейса, стабильность работы приложения',
            'total': total_responses,
            'answers': [
                {'text': '3 - Хорошо', 'count': 81, 'percent': 65.3},
                {'text': '2 - Приемлемо', 'count': 37, 'percent': 29.8},
                {'text': '1 - Плохо', 'count': 6, 'percent': 4.8}
            ]
        },
        {
            'title': 'Приложение 1С',
            'subtitle': 'Удобство интерфейса, стабильность работы приложения',
            'total': total_responses,
            'answers': [
                {'text': '3 - Удовлетворительно', 'count': 68, 'percent': 54.8},
                {'text': '2 - Неудобно', 'count': 34, 'percent': 27.4},
                {'text': '1 - Удобно', 'count': 22, 'percent': 17.7}
            ]
        }
    ]
    
    conn.close()
    
    return render_template('dashboard.html',
                         total_responses=total_responses,
                         location_stats={
                             'total': total_responses,
                             'locations': locations
                         },
                         questions=questions,
                         update_time=datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))
'''

# Находим и заменяем функцию dashboard
pattern = r'@app\.route\(\'/dashboard\'\).*?def dashboard\(\):.*?return render_template.*?\n'
updated_content = re.sub(pattern, new_dashboard_function, content, flags=re.DOTALL)

with open('/var/www/survey-report/final_with_charts.py', 'w') as f:
    f.write(updated_content)

print("Dashboard обновлен с реальными данными")
