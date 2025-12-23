#!/usr/bin/env python3
import sqlite3

print("🔍 ФИНАЛЬНАЯ ПРОВЕРКА ДАННЫХ")
print("="*60)

conn = sqlite3.connect('survey_complete.db')
cursor = conn.cursor()

print("📊 1. ДАННЫЕ ЛОКАЦИЙ:")
print("-"*60)

cursor.execute("""
    SELECT 
        name,
        category,
        responses,
        satisfaction,
        satisfaction * 10 as percent
    FROM locations 
    ORDER BY satisfaction DESC
""")

locations = cursor.fetchall()
print(f"{'Локация':<20} {'Тип':<10} {'Ответы':<8} {'Удовл.':<8} {'%':<6}")
print("-"*60)

total_responses = 0
for loc in locations:
    print(f"{loc[0]:<20} {loc[1]:<10} {loc[2]:<8} {loc[3]:<7.1f}/10 {loc[4]:<6.1f}%")
    total_responses += loc[2]

print(f"\n📈 Итого по локациям:")
print(f"   • Всего локаций: {len(locations)}")
print(f"   • Сумма ответов: {total_responses}")
print(f"   • Средняя удовлетворенность: {sum(l[3] for l in locations)/len(locations):.1f}/10")

print("\n❓ 2. ДАННЫЕ ВОПРОСОВ:")
print("-"*60)

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
        (positive_responses + neutral_responses + negative_responses) as sum_responses,
        ROUND(positive_responses * 100.0 / total_responses, 1) as calc_percent
    FROM questions 
    ORDER BY satisfaction_percent DESC
""")

questions = cursor.fetchall()
print(f"{'ID':<2} {'Категория':<20} {'Всего':<5} {'+':<3} {'~':<3} {'-':<3} {'% в БД':<6} {'% расч.':<7} {'Сумма':<5} {'OK'}")
print("-"*80)

for q in questions:
    status = "✅" if q[8] == q[3] and abs(q[9] - q[7]) < 1 else "⚠️"
    question_short = q[1][:20] + "..." if len(q[1]) > 20 else q[1]
    print(f"{q[0]:<2} {q[2]:<20} {q[3]:<5} {q[4]:<3} {q[5]:<3} {q[6]:<3} "
          f"{q[7]:<6.1f}% {q[9]:<7.1f}% {q[8]:<5} {status}")

print(f"\n📈 Итого по вопросам:")
print(f"   • Всего вопросов: {len(questions)}")
print(f"   • Ответов на каждый вопрос: {questions[0][3] if questions else 0}")
print(f"   • Средняя удовлетворенность: {sum(q[7] for q in questions)/len(questions):.1f}%")

print("\n🔗 3. СОГЛАСОВАННОСТЬ ДАННЫХ:")
print("-"*60)

# Проверяем согласованность
cursor.execute("SELECT DISTINCT total_responses FROM questions")
question_responses_list = [row[0] for row in cursor.fetchall()]

if question_responses_list:
    question_responses = question_responses_list[0]
    
    print(f"   • Локации (сумма ответов): {total_responses}")
    print(f"   • Вопросы (ответов на вопрос): {question_responses}")
    
    if total_responses == question_responses:
        print(f"   ✅ ОТЛИЧНО! Данные полностью согласованы")
    else:
        print(f"   ⚠️  ВНИМАНИЕ: Разница в {abs(total_responses - question_responses)} ответов")
        
        # Рекомендация
        if total_responses > 0:
            ratio = question_responses / total_responses
            print(f"   💡 Рекомендация: Умножить ответы в локациях на {ratio:.2f}")
else:
    print("   • Нет данных вопросов")

print("\n✅ 4. ДАННЫЕ ГОТОВЫ К ОТОБРАЖЕНИЮ:")
print("-"*60)

print("На странице локаций будет отображаться:")
print(f"   • Всего локаций: {len(locations)}")
print(f"   • Всего ответов: {total_responses}")
print(f"   • Средняя удовлетворенность: {sum(l[3] for l in locations)/len(locations):.1f}/10")

print("\nНа странице вопросов будет отображаться:")
if questions:
    print(f"   • Всего вопросов: {len(questions)}")
    print(f"   • Всего ответов: {question_responses}")
    print(f"   • Средняя удовлетворенность: {sum(q[7] for q in questions)/len(questions):.1f}%")
    print(f"   • Среднее на вопрос: {question_responses/len(questions):.1f} ответов")
else:
    print("   • Нет данных вопросов")

conn.close()

print("\n" + "="*60)
print("💡 Для применения изменений перезапустите сервер:")
print("   cd /var/www/survey-report")
print("   python3 final_with_charts.py")
