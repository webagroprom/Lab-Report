#!/usr/bin/env python3
import sqlite3

print("🔍 СРАВНЕНИЕ ДАННЫХ БАЗЫ С РЕАЛЬНОСТЬЮ")
print("="*50)

conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

# 1. Что должно быть по идее (из вашего TSV файла)
REAL_TOTAL_RESPONDENTS = 15  # Если у вас 15 строк в survey_data.tsv
print(f"\n1. РЕАЛЬНЫЕ ДАННЫЕ (предположительно):")
print(f"   • Респондентов всего: {REAL_TOTAL_RESPONDENTS}")
print(f"   • Ожидаемое в вопросах total_responses: {REAL_TOTAL_RESPONDENTS}")

# 2. Что есть в базе
print(f"\n2. ДАННЫЕ В БАЗЕ:")

# Локации
cursor.execute("SELECT SUM(responses) as total FROM locations")
db_location_total = cursor.fetchone()[0] or 0
print(f"   • Сумма ответов в локациях: {db_location_total}")

# Вопросы  
cursor.execute("SELECT DISTINCT total_responses FROM questions")
question_responses = [row[0] for row in cursor.fetchall() if row[0] is not None]
if question_responses:
    db_question_total = question_responses[0]
    print(f"   • Ответов в вопросах: {db_question_total}")
else:
    db_question_total = 0
    print(f"   • Ответов в вопросах: нет данных")

# 3. Сравнение
print(f"\n3. СРАВНЕНИЕ:")
print(f"   • Локации vs Реальность: {db_location_total} vs {REAL_TOTAL_RESPONDENTS}")

if db_question_total > 0:
    print(f"   • Вопросы vs Реальность: {db_question_total} vs {REAL_TOTAL_RESPONDENTS}")
    
    # Проверка согласованности
    if db_location_total == db_question_total == REAL_TOTAL_RESPONDENTS:
        print(f"\n✅ ИДЕАЛЬНО! Все данные согласованы с реальностью")
    elif db_location_total == db_question_total:
        print(f"\n⚠️  Данные согласованы между собой, но не с реальностью")
        print(f"   Разница с реальными данными: {abs(db_location_total - REAL_TOTAL_RESPONDENTS)} ответов")
    else:
        print(f"\n❌ НЕСОГЛАСОВАННОСТЬ в базе данных")
        print(f"   Локации: {db_location_total}, Вопросы: {db_question_total}")
else:
    print(f"   • Нет данных вопросов для сравнения")

# 4. Рекомендации
print(f"\n4. РЕКОМЕНДАЦИИ:")

if db_location_total != REAL_TOTAL_RESPONDENTS:
    diff = db_location_total - REAL_TOTAL_RESPONDENTS
    if diff > 0:
        print(f"   • Уменьшить ответы в локациях на {diff} (сейчас {db_location_total}, должно быть {REAL_TOTAL_RESPONDENTS})")
    else:
        print(f"   • Увеличить ответы в локациях на {-diff}")

if db_question_total != REAL_TOTAL_RESPONDENTS and db_question_total > 0:
    print(f"   • Обновить total_responses в вопросах на {REAL_TOTAL_RESPONDENTS}")

# 5. SQL команды для исправления
print(f"\n5. КОМАНДЫ ДЛЯ ИСПРАВЛЕНИЯ:")

if db_location_total != REAL_TOTAL_RESPONDENTS:
    print(f"   -- Обновить локации:")
    print(f"   UPDATE locations SET responses = responses * {REAL_TOTAL_RESPONDENTS / db_location_total:.2f};")

if db_question_total != REAL_TOTAL_RESPONDENTS and db_question_total > 0:
    print(f"   -- Обновить вопросы:")
    print(f"   UPDATE questions SET total_responses = {REAL_TOTAL_RESPONDENTS};")
    print(f"   -- Пересчитать positive/neutral/negative:")
    print(f"   UPDATE questions SET")
    print(f"       positive_responses = ROUND(total_responses * satisfaction_percent / 100),")
    print(f"       negative_responses = ROUND(total_responses * (100 - satisfaction_percent) * 0.3 / 100),")
    print(f"       neutral_responses = total_responses - positive_responses - negative_responses")
    print(f"   WHERE neutral_responses < 0;")

conn.close()
