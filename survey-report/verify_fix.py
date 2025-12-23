#!/usr/bin/env python3
import sqlite3

print("✅ ПРОВЕРКА ИСПРАВЛЕННЫХ ДАННЫХ")
print("="*50)

conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

print("1. ЛОКАЦИИ:")
cursor.execute("SELECT name, responses, satisfaction FROM locations ORDER BY satisfaction DESC")
print(f"{'Локация':<20} {'Ответы':<8} {'Удовл.'}")
print("-"*40)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:.1f}/10")

cursor.execute("SELECT SUM(responses) as total FROM locations")
total_loc = cursor.fetchone()[0]
print(f"\nВсего ответов в локациях: {total_loc}")

print("\n2. ВОПРОСЫ:")
cursor.execute("""
    SELECT 
        id,
        SUBSTR(question_text, 1, 30) || '...' as question,
        total_responses,
        positive_responses,
        neutral_responses,
        negative_responses,
        satisfaction_percent,
        (positive_responses + neutral_responses + negative_responses) as sum,
        CASE 
            WHEN (positive_responses + neutral_responses + negative_responses) = total_responses 
            THEN '✅' 
            ELSE '❌' 
        END as check
    FROM questions
    ORDER BY satisfaction_percent DESC
""")

print(f"{'ID':<3} {'Вопрос':<35} {'Всего':<5} {'+':<3} {'~':<3} {'-':<3} {'%':<6} {'Сумма':<5} {'OK'}")
print("-"*70)

all_ok = True
for row in cursor.fetchall():
    if row[8] == '❌':
        all_ok = False
    print(f"{row[0]:<3} {row[1]:<35} {row[2]:<5} {row[3]:<3} {row[4]:<3} {row[5]:<3} "
          f"{row[6]:5.1f}% {row[7]:<5} {row[8]}")

cursor.execute("SELECT DISTINCT total_responses FROM questions")
question_responses = cursor.fetchall()[0][0]
print(f"\nВсего ответов в вопросах: {question_responses}")

print("\n3. ИТОГОВАЯ ПРОВЕРКА:")
if total_loc == question_responses:
    print(f"✅ Локации и вопросы согласованы: {total_loc} ответов")
else:
    print(f"❌ НЕСОГЛАСОВАННОСТЬ: Локации={total_loc}, Вопросы={question_responses}")

if all_ok:
    print("✅ Все вопросы математически корректны")
else:
    print("❌ Есть проблемы в расчетах вопросов")

conn.close()

print("\n📊 РЕКОМЕНДАЦИИ ДЛЯ ВЕБ-ИНТЕРФЕЙСА:")
print(f"• На странице локаций будет: {total_loc} ответов")
print(f"• На странице вопросов будет: {question_responses} ответов")
print(f"• Среднее на вопрос: {question_responses}/8 = {question_responses/8:.1f}")
