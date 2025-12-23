#!/usr/bin/env python3
import sqlite3
import pandas as pd
from datetime import datetime

print("🔍 ПРОВЕРКА СОГЛАСОВАННОСТИ ДАННЫХ В БАЗЕ")
print("="*50)

# Подключаемся к базе
conn = sqlite3.connect('survey_complete.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n📊 1. СТАТИСТИКА ПО ЛОКАЦИЯМ:")
print("-"*50)

# Данные локаций
cursor.execute("SELECT COUNT(*) as count FROM locations")
total_locations = cursor.fetchone()['count']

cursor.execute("SELECT SUM(responses) as total_responses FROM locations")
total_location_responses = cursor.fetchone()['total_responses'] or 0

cursor.execute("SELECT AVG(satisfaction) as avg_satisfaction FROM locations")
avg_location_satisfaction = cursor.fetchone()['avg_satisfaction'] or 0

print(f"• Всего локаций: {total_locations}")
print(f"• Сумма ответов по локациям: {total_location_responses}")
print(f"• Средняя удовлетворенность: {avg_location_satisfaction:.1f}/10")

# Детали по локациям
cursor.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(responses) as responses,
        AVG(satisfaction) as avg_satisfaction
    FROM locations 
    GROUP BY category 
    ORDER BY responses DESC
""")
print("\n�� Распределение по категориям:")
for row in cursor.fetchall():
    print(f"  • {row['category']}: {row['count']} локаций, {row['responses']} ответов, ср.удовл.: {row['avg_satisfaction']:.1f}")

print("\n❓ 2. СТАТИСТИКА ПО ВОПРОСАМ:")
print("-"*50)

# Данные вопросов
cursor.execute("SELECT COUNT(*) as count FROM questions")
total_questions = cursor.fetchone()['count']

cursor.execute("SELECT DISTINCT total_responses FROM questions")
question_responses = [row['total_responses'] for row in cursor.fetchall()]

if question_responses:
    print(f"• Всего вопросов: {total_questions}")
    print(f"• Количество ответов в вопросах: {question_responses}")
    
    if len(set(question_responses)) == 1:
        print(f"  ✅ Все вопросы имеют одинаковое количество ответов: {question_responses[0]}")
    else:
        print(f"  ⚠️ ВНИМАНИЕ: Разное количество ответов в вопросах!")
        
    # Проверка согласованности с локациями
    if total_location_responses > 0 and question_responses[0] != total_location_responses:
        print(f"  ⚠️ НЕСОГЛАСОВАННОСТЬ: Локации: {total_location_responses} ответов, Вопросы: {question_responses[0]} ответов")
    elif total_location_responses > 0:
        print(f"  ✅ Согласованность: Локации и вопросы имеют одинаковое количество ответов: {total_location_responses}")
else:
    print("• Вопросов в базе нет")

print("\n📝 3. ДЕТАЛЬНЫЕ ДАННЫЕ ВОПРОСОВ:")
print("-"*50)

cursor.execute("""
    SELECT 
        id,
        question_text,
        category,
        total_responses,
        positive_responses,
        neutral_responses,
        negative_responses,
        satisfaction_percent,
        (positive_responses + neutral_responses + negative_responses) as calculated_total,
        CASE 
            WHEN (positive_responses + neutral_responses + negative_responses) = total_responses 
            THEN '✅' 
            ELSE '❌' 
        END as check_sum
    FROM questions 
    ORDER BY satisfaction_percent DESC
""")

questions = cursor.fetchall()
if questions:
    print(f"{'ID':<3} {'Удовл.':<6} {'Категория':<20} {'Всего':<6} {'+':<4} {'~':<4} {'-':<4} {'Сумма':<6} {'Проверка'}")
    print("-"*80)
    
    for q in questions:
        print(f"{q['id']:<3} {q['satisfaction_percent']:5.1f}% {q['category'][:18]:<20} "
              f"{q['total_responses']:<6} {q['positive_responses']:<4} {q['neutral_responses']:<4} "
              f"{q['negative_responses']:<4} {q['calculated_total']:<6} {q['check_sum']}")
        
    # Проверка математики
    print("\n🔢 ПРОВЕРКА РАСЧЕТОВ:")
    correct = sum(1 for q in questions if q['check_sum'] == '✅')
    print(f"• Правильно рассчитанные вопросы: {correct}/{len(questions)}")
    
    # Проверка satisfaction_percent
    problematic = []
    for q in questions:
        if q['total_responses'] > 0:
            calculated_percent = (q['positive_responses'] / q['total_responses'] * 100) if q['total_responses'] > 0 else 0
            diff = abs(calculated_percent - q['satisfaction_percent'])
            if diff > 0.1:  # Допускаем погрешность 0.1%
                problematic.append((q['id'], q['satisfaction_percent'], calculated_percent, diff))
    
    if problematic:
        print(f"  ⚠️ Проблемы с satisfaction_percent:")
        for prob in problematic:
            print(f"    ID {prob[0]}: в базе {prob[1]:.1f}%, рассчитано {prob[2]:.1f}%, разница {prob[3]:.1f}%")
else:
    print("Нет данных о вопросах")

print("\n✅ 4. СТАТИСТИКА ПО ЗАДАЧАМ:")
print("-"*50)

cursor.execute("SELECT COUNT(*) as count FROM tasks")
total_tasks = cursor.fetchone()['count']

cursor.execute("""
    SELECT 
        status,
        COUNT(*) as count,
        GROUP_CONCAT(task_key) as examples
    FROM tasks 
    GROUP BY status
""")
print(f"• Всего задач: {total_tasks}")
for row in cursor.fetchall():
    print(f"  • {row['status']}: {row['count']} задач")

print("\n📈 5. ИТОГОВАЯ СВОДКА:")
print("-"*50)

# Проверка общей согласованности
issues = []

# 1. Проверка локаций vs вопросы
if questions and total_location_responses != question_responses[0]:
    issues.append(f"Несовпадение ответов: Локации={total_location_responses}, Вопросы={question_responses[0]}")

# 2. Проверка математики в вопросах
if questions:
    math_errors = len([q for q in questions if q['check_sum'] == '❌'])
    if math_errors > 0:
        issues.append(f"Математические ошибки в {math_errors} вопросах")

# 3. Проверка satisfaction_percent
if problematic:
    issues.append(f"Неточности в satisfaction_percent для {len(problematic)} вопросов")

# 4. Проверка категорий локаций
cursor.execute("SELECT COUNT(DISTINCT category) as unique_categories FROM locations")
unique_cats = cursor.fetchone()['unique_categories']
print(f"• Уникальных категорий локаций: {unique_cats}")

cursor.execute("SELECT COUNT(DISTINCT category) as unique_categories FROM questions")
unique_question_cats = cursor.fetchone()['unique_categories']
print(f"• Уникальных категорий вопросов: {unique_question_cats}")

if issues:
    print("\n⚠️  ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
else:
    print("\n✅ Все данные согласованы и корректны!")

print("\n💡 РЕКОМЕНДАЦИИ:")
print("-"*50)

if total_location_responses < 10:
    print("1. Мало данных в локациях - рассмотрите импорт реальных данных")
elif total_location_responses > 1000:
    print("1. Очень много данных - проверьте реалистичность")

if not questions:
    print("2. Нет данных вопросов - заполните таблицу questions")
elif len(set(question_responses)) > 1:
    print("2. Приведите количество ответов во всех вопросах к одному значению")

if total_tasks == 0:
    print("3. Нет данных о задачах - заполните таблицу tasks")

conn.close()

print(f"\n📅 Проверка завершена: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
