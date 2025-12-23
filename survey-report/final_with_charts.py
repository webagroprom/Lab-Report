#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64
import json
import os
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'survey-report-secret-2025'
app.config['UPLOAD_FOLDER'] = '/var/www/survey-report/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def init_db():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            responses INTEGER DEFAULT 0,
            satisfaction REAL DEFAULT 0.0,
            problems TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            category TEXT,
            total_responses INTEGER DEFAULT 0,
            positive_responses INTEGER DEFAULT 0,
            neutral_responses INTEGER DEFAULT 0,
            negative_responses INTEGER DEFAULT 0,
            satisfaction_percent REAL DEFAULT 0.0,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_key TEXT NOT NULL,
            summary TEXT,
            status TEXT,
            category TEXT,
            location TEXT,
            priority INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('/var/www/survey-report/survey_complete.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_satisfaction_chart(locations):
    if not locations:
        return None
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    loc_names = [loc['name'] for loc in locations]
    satisfaction_scores = [loc['satisfaction'] for loc in locations]
    responses = [loc['responses'] for loc in locations]
    
    sorted_indices = sorted(range(len(satisfaction_scores)), 
                          key=lambda i: satisfaction_scores[i], 
                          reverse=True)
    loc_names = [loc_names[i] for i in sorted_indices]
    satisfaction_scores = [satisfaction_scores[i] for i in sorted_indices]
    responses = [responses[i] for i in sorted_indices]
    
    colors = []
    for score in satisfaction_scores:
        if score >= 8:
            colors.append('#27ae60')
        elif score >= 6:
            colors.append('#f1c40f')
        else:
            colors.append('#e74c3c')
    
    bars = ax.barh(loc_names, satisfaction_scores, color=colors)
    ax.set_xlabel('Удовлетворенность (из 10)', fontsize=12)
    ax.set_title('Удовлетворенность по локациям', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 10)
    
    for bar, score, resp in zip(bars, satisfaction_scores, responses):
        width = bar.get_width()
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2,
               f'{score:.1f} ({resp} отв.)', ha='left', va='center')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    return img_base64

def create_questions_chart(questions):
    if not questions:
        return None
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    question_texts = [q['question_text'][:30] + '...' if len(q['question_text']) > 30 else q['question_text'] 
                     for q in questions]
    satisfaction = [q['satisfaction_percent'] for q in questions]
    
    sorted_indices = sorted(range(len(satisfaction)), key=lambda i: satisfaction[i])
    question_texts = [question_texts[i] for i in sorted_indices]
    satisfaction = [satisfaction[i] for i in sorted_indices]
    
    colors = plt.cm.viridis([s/100 for s in satisfaction])
    bars = ax.barh(question_texts, satisfaction, color=colors)
    
    ax.set_xlabel('Процент удовлетворенности', fontsize=12)
    ax.set_title('Удовлетворенность по вопросам', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 100)
    
    for bar, score in zip(bars, satisfaction):
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2,
               f'{score:.1f}%', ha='left', va='center')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    return img_base64

@app.route('/')
def index():
    return redirect('/locations')

@app.route('/locations')
def locations():
    conn = get_db_connection()
    locations_data = conn.execute('SELECT * FROM locations ORDER BY satisfaction DESC').fetchall()
    conn.close()
    
    locations_list = []
    total_responses = 0
    total_satisfaction = 0
    
    for loc in locations_data:
        loc_dict = dict(loc)
        loc_dict['css_class'] = f"location-{loc_dict.get('category', 'default')}"
        locations_list.append(loc_dict)
        total_responses += loc_dict.get('responses', 0)
        total_satisfaction += loc_dict.get('satisfaction', 0)
    
    avg_satisfaction = total_satisfaction / len(locations_list) if locations_list else 0
    
    chart = create_satisfaction_chart(locations_list)
    
    return render_template('locations.html',
                         locations=locations_list,
                         total_responses=total_responses,
                         avg_satisfaction=round(avg_satisfaction, 1),
                         chart=chart,
                         now_time=datetime.now().strftime('%d.%m.%Y %H:%M'))

@app.route('/questions')
def questions():
    conn = get_db_connection()
    questions_data = conn.execute('SELECT * FROM questions ORDER BY satisfaction_percent DESC').fetchall()
    conn.close()
    
    questions_list = []
    total_questions = len(questions_data)
    
    # ВАЖНО: total_responses - это количество РЕСПОНДЕНТОВ, а не сумма ответов на все вопросы
    # Предполагаем, что все вопросы были заданы одним и тем же людям
    # Поэтому берем максимальное значение ответов среди всех вопросов
    total_responses = 0
    if questions_data:
        # Берем первое значение (все вопросы должны иметь одинаковое количество респондентов)
        total_responses = questions_data[0]['total_responses']
    
    avg_satisfaction = 0
    
    for q in questions_data:
        q_dict = dict(q)
        questions_list.append(q_dict)
        avg_satisfaction += q_dict.get('satisfaction_percent', 0)
    
    avg_satisfaction = avg_satisfaction / total_questions if total_questions > 0 else 0
    
    chart = create_questions_chart(questions_list)
    
    return render_template('questions.html',
                         questions=questions_list,
                         total_questions=total_questions,
                         total_responses=total_responses,  # Теперь это количество респондентов
                         avg_satisfaction=round(avg_satisfaction, 1),
                         chart=chart,
                         now_time=datetime.now().strftime('%d.%m.%Y %H:%M'))

@app.route('/tasks')
def tasks():
    conn = get_db_connection()
    tasks_data = conn.execute('SELECT * FROM tasks ORDER BY priority ASC, created_at DESC').fetchall()
    conn.close()
    
    tasks_list = [dict(task) for task in tasks_data]
    completed_tasks = sum(1 for t in tasks_list if 'Выполнено' in str(t.get('status', '')))
    total_tasks = len(tasks_list)
    
    return render_template('tasks_simple.html',
                         tasks=tasks_list,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         now_time=datetime.now().strftime('%d.%m.%Y %H:%M'))

@app.route('/import', methods=['GET', 'POST'])
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        import_type = request.form.get('import_type', 'locations')
        
        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                conn = get_db_connection()
                
                if import_type == 'locations':
                    df = pd.read_excel(filepath)
                    for _, row in df.iterrows():
                        conn.execute('''
                            INSERT OR REPLACE INTO locations (name, category, responses, satisfaction, problems)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            str(row.iloc[0]) if len(row) > 0 else '',
                            str(row.iloc[1]) if len(row) > 1 else '',
                            int(row.iloc[2]) if len(row) > 2 else 0,
                            float(row.iloc[3]) if len(row) > 3 else 0.0,
                            str(row.iloc[4]) if len(row) > 4 else ''
                        ))
                    flash(f'Импортировано {len(df)} локаций', 'success')
                    
                elif import_type == 'questions':
                    df = pd.read_excel(filepath)
                    for _, row in df.iterrows():
                        conn.execute('''
                            INSERT OR REPLACE INTO questions 
                            (question_text, category, total_responses, positive_responses, 
                             neutral_responses, negative_responses, satisfaction_percent, location)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            str(row.iloc[0]) if len(row) > 0 else '',
                            str(row.iloc[1]) if len(row) > 1 else '',
                            int(row.iloc[2]) if len(row) > 2 else 0,
                            int(row.iloc[3]) if len(row) > 3 else 0,
                            int(row.iloc[4]) if len(row) > 4 else 0,
                            int(row.iloc[5]) if len(row) > 5 else 0,
                            float(row.iloc[6]) if len(row) > 6 else 0.0,
                            str(row.iloc[7]) if len(row) > 7 else ''
                        ))
                    flash(f'Импортировано {len(df)} вопросов', 'success')
                    
                elif import_type == 'tasks':
                    df = pd.read_excel(filepath)
                    for _, row in df.iterrows():
                        conn.execute('''
                            INSERT OR REPLACE INTO tasks (task_key, summary, status, category, location, priority)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            str(row.iloc[0]) if len(row) > 0 else '',
                            str(row.iloc[1]) if len(row) > 1 else '',
                            str(row.iloc[2]) if len(row) > 2 else 'В работе',
                            str(row.iloc[3]) if len(row) > 3 else '',
                            str(row.iloc[4]) if len(row) > 4 else '',
                            int(row.iloc[5]) if len(row) > 5 else 3
                        ))
                    flash(f'Импортировано {len(df)} задач', 'success')
                
                conn.commit()
                conn.close()
                
            except Exception as e:
                flash(f'Ошибка импорта: {str(e)}', 'error')
            
            return redirect('/import')
    
    return render_template('import_simple.html',
                         now_time=datetime.now().strftime('%d.%m.%Y %H:%M'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    print("🚀 Запуск Survey Report Dashboard на порту 5004")
    print("📊 Доступные маршруты:")
    print("   • http://localhost:5004/locations - Локации")
    print("   • http://localhost:5004/questions - Вопросы (исправленный подсчет)")
    print("   • http://localhost:5004/tasks - Задачи")
    print("   • http://localhost:5004/import - Импорт данных")
    
    app.run(host='0.0.0.0', port=5004, debug=True)
