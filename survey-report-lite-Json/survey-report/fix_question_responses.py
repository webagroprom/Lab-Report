#!/usr/bin/env python3
import sqlite3

# Подключаемся к базе
conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

# Предположим, что у вас было 115 респондентов (как в тестовых данных)
# Если у вас другое количество, измените это значение
REAL_RESPONDENTS = 115

print(f"Исправляем данные для {REAL_RESPONDENTS} респондентов...")

# Обновляем количество ответов для всех вопросов
cursor.execute("UPDATE questions SET total_responses = ?", (REAL_RESPONDENTS,))

# Проверяем
cursor.execute("SELECT question_text, total_responses FROM questions")
questions = cursor.fetchall()

print("\nОбновленные данные:")
print("="*50)
for question, responses in questions:
    print(f"{question[:50]}... : {responses} ответов")

conn.commit()
conn.close()

print(f"\n✅ Все вопросы теперь имеют {REAL_RESPONDENTS} ответов")
print("Это количество респондентов, а не сумма ответов на все вопросы")
