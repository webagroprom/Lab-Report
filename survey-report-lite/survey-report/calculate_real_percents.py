#!/usr/bin/env python3
import pandas as pd
import numpy as np

print("📊 ТОЧНЫЙ РАСЧЕТ ПРОЦЕНТОВ УДОВЛЕТВОРЕННОСТИ ИЗ TSV")
print("="*60)

# Загрузка данных
df = pd.read_csv('survey_data.tsv', sep='\t')

# Колонки с вопросами
yan_col = 'На сколько вы удовлетворены приложениями семейства Яндекс ? / Удобство интерфейса, стабильность работы приложения'
office_col = 'На сколько вы удовлетворены работой пакетов MS Office ?  / Удобство интерфейса, стабильность работы приложения'
onec_col = 'Как вы оцениваете работу приложения 1С ? / Удобство интерфейса, стабильность работы приложения'

print(f"Всего строк в данных: {len(df)}")

# Функция для расчета процента удовлетворенности
def calculate_satisfaction(series, mapping):
    """Рассчитывает процент удовлетворенности на основе mapping"""
    total = series.count()
    if total == 0:
        return 0
    
    # Подсчет оценок
    counts = series.value_counts()
    score_sum = 0
    
    for value, count in counts.items():
        if value in mapping:
            score_sum += count * mapping[value]
    
    return (score_sum / total)

# Маппинг оценок для Яндекса и MS Office
# 1 - Плохо = 0%, 2 - Приемлемо = 50%, 3 - Хорошо = 100%
yan_office_mapping = {
    '1 - Плохо': 0,
    '2 - Приемлемо': 50,
    '3 - Хорошо': 100
}

# Маппинг оценок для 1С
# 1 - Удобно = 100%, 2 - Неудобно = 0%, 3 - Удовлетворительно = 50%
onec_mapping = {
    '1 - Удобно': 100,
    '2 - Неудобно': 0,
    '3 - Удовлетворительно': 50
}

print("\n📈 РАСЧЕТ РЕАЛЬНЫХ ПРОЦЕНТОВ:")
print("-"*60)

# Яндекс
yan_series = df[yan_col]
yan_percent = calculate_satisfaction(yan_series, yan_office_mapping)
print(f"1. Яндекс приложения: {yan_percent:.1f}%")
print(f"   Всего ответов: {yan_series.count()}")

# MS Office
office_series = df[office_col]
office_percent = calculate_satisfaction(office_series, yan_office_mapping)
print(f"2. MS Office: {office_percent:.1f}%")
print(f"   Всего ответов: {office_series.count()}")

# 1С
onec_series = df[onec_col]
onec_percent = calculate_satisfaction(onec_series, onec_mapping)
print(f"3. 1С: {onec_percent:.1f}%")
print(f"   Всего ответов: {onec_series.count()}")

print("\n📊 РАСПРЕДЕЛЕНИЕ ОТВЕТОВ:")
print("-"*60)

print("Яндекс приложения:")
yan_counts = yan_series.value_counts()
for value, count in yan_counts.items():
    percent = count / yan_series.count() * 100
    print(f"  {value}: {count} ({percent:.1f}%)")

print("\nMS Office:")
office_counts = office_series.value_counts()
for value, count in office_counts.items():
    percent = count / office_series.count() * 100
    print(f"  {value}: {count} ({percent:.1f}%)")

print("\n1С:")
onec_counts = onec_series.value_counts()
for value, count in onec_counts.items():
    percent = count / onec_series.count() * 100
    print(f"  {value}: {count} ({percent:.1f}%)")

print("\n🚀 SQL-КОМАНДЫ ДЛЯ ОБНОВЛЕНИЯ БАЗЫ:")
print("-"*60)

print(f"-- Для {len(df)} респондентов:")
print(f"UPDATE questions SET total_responses = {len(df)};")
print()
print(f"-- Яндекс: {yan_percent:.1f}%")
yan_pos = int(len(df) * (yan_counts.get('3 - Хорошо', 0) / yan_series.count()))
yan_neu = int(len(df) * (yan_counts.get('2 - Приемлемо', 0) / yan_series.count()))
yan_neg = len(df) - yan_pos - yan_neu
print(f"UPDATE questions SET satisfaction_percent = {yan_percent:.1f}, positive_responses = {yan_pos}, neutral_responses = {yan_neu}, negative_responses = {yan_neg} WHERE id = 1;")
print()
print(f"-- MS Office: {office_percent:.1f}%")
office_pos = int(len(df) * (office_counts.get('3 - Хорошо', 0) / office_series.count()))
office_neu = int(len(df) * (office_counts.get('2 - Приемлемо', 0) / office_series.count()))
office_neg = len(df) - office_pos - office_neu
print(f"UPDATE questions SET satisfaction_percent = {office_percent:.1f}, positive_responses = {office_pos}, neutral_responses = {office_neu}, negative_responses = {office_neg} WHERE id = 2;")
print()
print(f"-- 1С: {onec_percent:.1f}%")
onec_pos = int(len(df) * (onec_counts.get('1 - Удобно', 0) / onec_series.count()))
onec_neu = int(len(df) * (onec_counts.get('3 - Удовлетворительно', 0) / onec_series.count()))
onec_neg = len(df) - onec_pos - onec_neu
print(f"UPDATE questions SET satisfaction_percent = {onec_percent:.1f}, positive_responses = {onec_pos}, neutral_responses = {onec_neu}, negative_responses = {onec_neg} WHERE id = 3;")

print("\n✅ Расчет завершен!")
