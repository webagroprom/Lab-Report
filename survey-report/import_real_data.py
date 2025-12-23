#!/usr/bin/env python3
import sqlite3
import pandas as pd

# Читаем реальные данные
df = pd.read_csv('survey_data.tsv', sep='\t')
print(f"Всего строк в survey_data.tsv: {len(df)}")

# Подсчитываем ответы по локациям
location_counts = df['Локация'].value_counts()
print("\nРаспределение по локациям:")
print(location_counts)

# Подключаемся к базе
conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

# Очищаем старые данные
cursor.execute("DELETE FROM locations")
cursor.execute("DELETE FROM questions")

# Вставляем реальные данные локаций
for location, count in location_counts.items():
    # Примерная удовлетворенность (нужно рассчитать из реальных данных)
    satisfaction = 7.0  # Заменить на реальный расчет
    
    cursor.execute('''
        INSERT INTO locations (name, category, responses, satisfaction)
        VALUES (?, ?, ?, ?)
    ''', (
        location,
        'factory' if 'Завод' in location else 'office',
        int(count),
        float(satisfaction)
    ))

# Обновляем вопросы с реальным количеством респондентов
total_respondents = len(df)
cursor.execute("UPDATE questions SET total_responses = ?", (total_respondents,))

conn.commit()
conn.close()

print(f"\n✅ Импортировано {len(location_counts)} локаций")
print(f"✅ Всего респондентов: {total_respondents}")
print(f"✅ Обновлены вопросы: {total_respondents} ответов")
