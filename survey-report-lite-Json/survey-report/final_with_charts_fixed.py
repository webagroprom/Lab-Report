#!/usr/bin/env python3
"""
Dashboard for survey results with charts - FIXED VERSION for old database schema.
"""
import sqlite3
import json
from collections import Counter, defaultdict
import math
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
import os
import pandas as pd
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.secret_key = 'survey-secret-key-2025'  # For flash messages

# Custom Jinja2 filter for getting basename
@app.template_filter('basename')
def basename_filter(path):
    """Get basename from path."""
    return os.path.basename(path) if path else ''

# Database path
DB_PATH = 'survey_complete.db'

def get_db_connection():
    """Create database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_survey_statistics():
    """Get survey statistics from the JSON file directly."""
    # Try different possible locations for the JSON file
    json_file_paths = [
        'uploads/survey_data.json',
        'uploads/2025-12-23_Opros_udovletvorennosti_nastroikoi_PK_i_soputstvuiushchego_PO.json',
        '2025-12-23_Opros_udovletvorennosti_nastroikoi_PK_i_soputstvuiushchego_PO.json',
    ]
    
    json_data = None
    json_file_path = None
    
    for path in json_file_paths:
        if os.path.exists(path):
            json_file_path = path
            break
    
    if not json_file_path:
        print("No JSON file found")
        return {'total_responses': 0, 'locations': Counter(), 'questions': {}, 'overall_satisfaction': Counter()}
    
    print(f"Reading JSON from: {json_file_path}")
    
    # Read JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return {'total_responses': 0, 'locations': Counter(), 'questions': {}, 'overall_satisfaction': Counter()}
    
    stats = {
        'total_responses': len(data),
        'locations': Counter(),
        'questions': defaultdict(lambda: {
            'total': 0,
            'answers': Counter(),
            'sub_questions': defaultdict(lambda: {'total': 0, 'answers': Counter()})
        }),
        'overall_satisfaction': Counter(),
        'free_text_questions': defaultdict(list)
    }
    
    for respondent_data in data:
        location = None
        overall_satisfaction = None
        
        # First pass: find location and overall satisfaction
        for item in respondent_data:
            if isinstance(item, list) and len(item) >= 2:
                question = item[0]
                answer = item[1]
                
                if "локацию" in question.lower() or "вашу локацию" in question.lower():
                    location = answer
                    stats['locations'][answer] += 1
                
                if "Общая удовлетворенность рабочего места" in question and "/" not in question:
                    try:
                        if isinstance(answer, (int, float)):
                            overall_satisfaction = int(answer)
                        elif isinstance(answer, str) and answer.strip().isdigit():
                            overall_satisfaction = int(answer.strip())
                        if overall_satisfaction:
                            stats['overall_satisfaction'][str(overall_satisfaction)] += 1
                    except:
                        pass
        
        # Second pass: process all questions
        for item in respondent_data:
            if not isinstance(item, list) or len(item) < 2:
                continue
            
            question = item[0]
            answer = item[1]
            
            if not question or not question.strip():
                continue
            
            # Skip location and overall satisfaction (already processed)
            if "локацию" in question.lower() or "вашу локацию" in question.lower():
                continue
            
            if "Общая удовлетворенность рабочего места" in question and "/" not in question:
                continue
            
            # Process the question
            question_key = question
            
            # Handle questions with sub-questions (text after "/")
            if "/" in question:
                main_q, sub_q = question.split("/", 1)
                main_q = main_q.strip()
                sub_q = sub_q.strip()
                
                stats['questions'][main_q]['total'] += 1
                
                # Process answer
                if answer and str(answer).strip():
                    if " - " in str(answer):
                        # Rating answer like "3 - Хорошо"
                        stats['questions'][main_q]['sub_questions'][sub_q]['answers'][str(answer)] += 1
                    else:
                        # Text answer
                        stats['questions'][main_q]['sub_questions'][sub_q]['answers'][str(answer)] += 1
                    stats['questions'][main_q]['sub_questions'][sub_q]['total'] += 1
            else:
                # Simple question
                stats['questions'][question_key]['total'] += 1
                
                if answer and str(answer).strip():
                    # Check if this is a free text question
                    is_free_text = any(keyword in question.lower() for keyword in 
                                     ['предложения', 'предложение', 'какие дополнительные', 'покрывают ваши потребности'])
                    
                    if is_free_text:
                        stats['free_text_questions'][question_key].append(str(answer))
                    else:
                        stats['questions'][question_key]['answers'][str(answer)] += 1
    
    return stats

def generate_chart_image(data_dict, title, chart_type='bar'):
    """Generate a chart image and return as base64 string."""
    if not data_dict:
        return None
    
    plt.figure(figsize=(10, 6))
    
    # Prepare data
    labels = list(data_dict.keys())
    values = list(data_dict.values())
    
    if chart_type == 'bar':
        bars = plt.bar(labels, values)
        plt.xticks(rotation=45, ha='right')
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                    f'{value}', ha='center', va='bottom', fontsize=9)
    
    elif chart_type == 'pie':
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
    
    plt.title(title)
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    
    # Convert to base64
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    
    return img_base64

@app.route('/')
def dashboard():
    """Main dashboard page."""
    stats = get_survey_statistics()
    
    # Prepare data for template
    total_responses = stats['total_responses']
    
    # Location statistics
    locations_sorted = sorted(stats['locations'].items(), key=lambda x: x[1], reverse=True)
    location_data = []
    for loc, count in locations_sorted:
        percentage = (count / total_responses * 100) if total_responses > 0 else 0
        location_data.append({
            'name': loc,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    # Questions data
    questions_data = []
    for q_text, q_data in stats['questions'].items():
        if q_data['total'] > 0:
            # Check if this question has sub-questions
            if q_data['sub_questions']:
                for sub_q_text, sub_q_data in q_data['sub_questions'].items():
                    if sub_q_data['total'] > 0:
                        answers_sorted = sorted(sub_q_data['answers'].items(), 
                                               key=lambda x: x[1], 
                                               reverse=True)
                        
                        answers_list = []
                        for ans, count in answers_sorted:
                            percentage = (count / sub_q_data['total'] * 100) if sub_q_data['total'] > 0 else 0
                            answers_list.append({
                                'text': ans,
                                'count': count,
                                'percentage': round(percentage, 1)
                            })
                        
                        questions_data.append({
                            'question': q_text,
                            'sub_question': sub_q_text,
                            'total': sub_q_data['total'],
                            'answers': answers_list,
                            'has_sub_question': True
                        })
            else:
                # Question without sub-questions
                answers_sorted = sorted(q_data['answers'].items(), 
                                       key=lambda x: x[1], 
                                       reverse=True)
                
                answers_list = []
                for ans, count in answers_sorted:
                    percentage = (count / q_data['total'] * 100) if q_data['total'] > 0 else 0
                    answers_list.append({
                        'text': ans,
                        'count': count,
                        'percentage': round(percentage, 1)
                    })
                
                questions_data.append({
                    'question': q_text,
                    'sub_question': None,
                    'total': q_data['total'],
                    'answers': answers_list,
                    'has_sub_question': False
                })
    
    # Overall satisfaction
    satisfaction_sorted = sorted(stats['overall_satisfaction'].items(), 
                               key=lambda x: int(x[0]) if x[0].isdigit() else 0)
    satisfaction_data = []
    for score, count in satisfaction_sorted:
        percentage = (count / total_responses * 100) if total_responses > 0 else 0
        satisfaction_data.append({
            'score': score,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    # Free text questions
    free_text_data = []
    for q_text, responses in stats['free_text_questions'].items():
        if responses:
            free_text_data.append({
                'question': q_text,
                'response_count': len(responses),
                'responses': responses[:10],
                'has_more': len(responses) > 10
            })
    
    # Problem frequency data
    problem_data = []
    for q_text, q_data in stats['questions'].items():
        if "проблемами вы сталкиваетесь" in q_text.lower():
            if q_data['answers']:
                answers_sorted = sorted(q_data['answers'].items(), 
                                       key=lambda x: x[1], 
                                       reverse=True)
                
                total_problems = sum(q_data['answers'].values())
                for ans, count in answers_sorted:
                    if ans.strip():  # Skip empty answers
                        percentage = (count / total_problems * 100) if total_problems > 0 else 0
                        problem_data.append({
                            'problem': ans,
                            'count': count,
                            'percentage': round(percentage, 1)
                        })
    
    # Generate charts
    charts = {}
    
    # Location chart
    if location_data:
        loc_dict = {item['name']: item['count'] for item in location_data if item['count'] > 0}
        if loc_dict:
            charts['locations'] = generate_chart_image(loc_dict, 'Распределение по локациям', 'bar')
    
    # Overall satisfaction chart
    if satisfaction_data:
        sat_dict = {item['score']: item['count'] for item in satisfaction_data}
        if sat_dict:
            charts['satisfaction'] = generate_chart_image(sat_dict, 'Общая удовлетворенность', 'bar')
    
    # Problem frequency chart
    if problem_data:
        prob_dict = {item['problem']: item['count'] for item in problem_data}
        if prob_dict:
            charts['problems'] = generate_chart_image(prob_dict, 'Частота проблем', 'bar')
    
    # Get current file info
    current_file = None
    json_file_paths = [
        'uploads/survey_data.json',
        'uploads/2025-12-23_Opros_udovletvorennosti_nastroikoi_PK_i_soputstvuiushchego_PO.json',
    ]
    
    for path in json_file_paths:
        if os.path.exists(path):
            current_file = path
            break
    
    return render_template('dashboard.html',
                         total_responses=total_responses,
                         location_data=location_data,
                         questions_data=questions_data,
                         satisfaction_data=satisfaction_data,
                         free_text_data=free_text_data,
                         problem_data=problem_data,
                         charts=charts,
                         current_file=current_file,
                         now=datetime.now())

@app.route('/import')
def import_page():
    """Page for importing JSON data."""
    # Get current file info
    current_file = None
    current_file_exists = False
    json_file_paths = [
        'uploads/survey_data.json',
        'uploads/2025-12-23_Opros_udovletvorennosti_nastroikoi_PK_i_soputstvuiushchego_PO.json',
    ]
    
    for path in json_file_paths:
        if os.path.exists(path):
            current_file = path
            current_file_exists = True
            break
    
    return render_template('import_simple.html', 
                         current_file=current_file,
                         current_file_exists=current_file_exists)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        flash('❌ Ошибка: Файл не выбран', 'error')
        return redirect(url_for('import_page'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('❌ Ошибка: Файл не выбран', 'error')
        return redirect(url_for('import_page'))
    
    if file and file.filename.endswith('.json'):
        try:
            # First, validate JSON
            file_content = file.read()
            file.seek(0)  # Reset file pointer
            
            # Try to parse JSON
            data = json.loads(file_content.decode('utf-8'))
            
            if not isinstance(data, list):
                flash('❌ Ошибка: JSON должен быть массивом', 'error')
                return redirect(url_for('import_page'))
            
            # Check if data has the expected structure
            if len(data) == 0:
                flash('❌ Ошибка: JSON файл пустой', 'error')
                return redirect(url_for('import_page'))
            
            # Save the file
            filename = 'uploads/survey_data.json'
            os.makedirs('uploads', exist_ok=True)
            file.save(filename)
            
            # Count responses
            response_count = len(data)
            
            flash(f'✅ Успешно! Загружено {response_count} ответов из файла {file.filename}', 'success')
            return redirect(url_for('dashboard'))
            
        except json.JSONDecodeError as e:
            flash(f'❌ Ошибка JSON: {str(e)}', 'error')
            return redirect(url_for('import_page'))
        except Exception as e:
            flash(f'❌ Ошибка: {str(e)}', 'error')
            return redirect(url_for('import_page'))
    else:
        flash('❌ Ошибка: Файл должен быть в формате JSON (.json)', 'error')
        return redirect(url_for('import_page'))

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics."""
    stats = get_survey_statistics()
    return jsonify(stats)

@app.route('/api/export/csv')
def export_csv():
    """Export data as CSV."""
    stats = get_survey_statistics()
    
    # Create DataFrame
    data = []
    for loc, count in stats['locations'].items():
        data.append({'Тип': 'Локация', 'Название': loc, 'Количество': count})
    
    for q_text, q_data in stats['questions'].items():
        for answer, count in q_data['answers'].items():
            data.append({'Тип': 'Вопрос', 'Вопрос': q_text, 'Ответ': answer, 'Количество': count})
    
    df = pd.DataFrame(data)
    
    # Save to CSV
    csv_path = 'survey_export.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    return send_file(csv_path, as_attachment=True, download_name='survey_results.csv')

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
