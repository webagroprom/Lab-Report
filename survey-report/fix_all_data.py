#!/usr/bin/env python3
import sqlite3

print("🔧 ИСПРАВЛЕНИЕ ДАННЫХ В БАЗЕ")
print("="*50)

conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

REAL_TOTAL_RESPONDENTS = 15  # У вас реально 15 респондентов

print(f"1. Обновляем локации на {REAL_TOTAL_RESPONDENTS} ответов...")

# Обновляем локации пропорционально
cursor.execute("""
    UPDATE locations 
    SET responses = ROUND(responses * ? / (SELECT SUM(responses) FROM locations))
""", (REAL_TOTAL_RESPONDENTS,))

# Проверяем
cursor.execute("SELECT SUM(responses) as total FROM locations")
new_total = cursor.fetchone()[0]
print(f"   ✅ Новое общее количество: {new_total}")

print(f"\n2. Обновляем вопросы на {REAL_TOTAL_RESPONDENTS} ответов...")

# Сначала обновляем total_responses
cursor.execute("UPDATE questions SET total_responses = ?", (REAL_TOTAL_RESPONDENTS,))

# Пересчитываем positive/neutral/negative на основе satisfaction_percent
print("   Пересчитываем распределение ответов...")
cursor.execute("""
    UPDATE questions 
    SET 
        positive_responses = ROUND(total_responses * satisfaction_percent / 100),
        negative_responses = ROUND(total_responses * (100 - satisfaction_percent) * 0.4 / 100),
        neutral_responses = total_responses - positive_responses - negative_responses
""")

# Исправляем возможные отрицательные neutral_responses
cursor.execute("""
    UPDATE questions 
    SET 
        negative_responses = ROUND(total_responses * (100 - satisfaction_percent) * 0.3 / 100),
        neutral_responses = total_responses - positive_responses - negative_responses
    WHERE neutral_responses < 0
""")

cursor.execute("""
    UPDATE questions 
    SET 
        negative_responses = ROUND(total_responses * (100 - satisfaction_percent) * 0.2 / 100),
        neutral_responses = total_responses - positive_responses - negative_responses
    WHERE neutral_responses < 0
""")

# Проверяем
cursor.execute("""
    SELECT 
        id,
        question_text,
        total_responses,
        positive_responses,
        neutral_responses,
        negative_responses,
        satisfaction_percent,
        (positive_responses + neutral_responses + negative_responses) as calculated_total,
        ROUND(positive_responses * 100.0 / total_responses, 1) as calculated_percent
    FROM questions
""")

print("\n3. Проверка исправленных вопросов:")
print(f"{'ID':<3} {'Удовл.':<6} {'Всего':<5} {'+':<3} {'~':<3} {'-':<3} {'Сумма':<5} {'Расч.%':<6} {'Статус'}")
print("-"*70)

questions = cursor.fetchall()
for q in questions:
    status = "✅" if q['calculated_total'] == q['total_responses'] and abs(q['calculated_percent'] - q['satisfaction_percent']) < 1 else "⚠️"
    print(f"{q['id']:<3} {q['satisfaction_percent']:5.1f}% {q['total_responses']:<5} "
          f"{q['positive_responses']:<3} {q['neutral_responses']:<3} {q['negative_responses']:<3} "
          f"{q['calculated_total']:<5} {q['calculated_percent']:5.1f}% {status}")

conn.commit()
conn.close()

print(f"\n✅ Данные исправлены!")
print(f"   • Локации: {new_total} ответов")
print(f"   • Вопросы: {REAL_TOTAL_RESPONDENTS} ответов на каждый вопрос")
