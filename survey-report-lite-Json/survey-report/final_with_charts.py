#!/usr/bin/env python3
"""
Dashboard for survey results with charts.
This version correctly separates questions and keeps proper formatting.
"""
import sqlite3
import json
from collections import Counter, defaultdict
import math
from flask import Flask, render_template, request, jsonify, send_file
import os
import pandas as pd
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

# Database path
DB_PATH = 'survey_complete.db'

def get_db_connection():
    """Create database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_responses():
    """Get all responses from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            r.id as response_id,
            r.location,
            r.overall_satisfaction,
            qr.question_id,
            qr.question_text,
            qr.answer_text,
            qr.rating_value,
            qr.is_rating,
            q.original_text,
            q.question_type
        FROM responses r
        LEFT JOIN question_responses qr ON r.id = qr.response_id
        LEFT JOIN questions q ON qr.question_id = q.id
        ORDER BY r.id, qr.question_id
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def get_all_locations():
    """Get all unique locations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT location FROM responses WHERE location IS NOT NULL AND location != '' ORDER BY location")
    locations = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return locations

def get_survey_statistics():
    """Get comprehensive survey statistics with proper question grouping."""
    rows = get_all_responses()
    
    # Initialize data structures
    stats = {
        'total_responses': 0,
        'locations': Counter(),
        'questions': defaultdict(lambda: {
            'total': 0,
            'answers': Counter(),
            'sub_questions': defaultdict(lambda: {'total': 0, 'answers': Counter()})
        }),
        'overall_satisfaction': Counter(),
        'free_text_questions': defaultdict(list)
    }
    
    # Track seen response IDs
    seen_response_ids = set()
    
    for row in rows:
        response_id = row['response_id']
        
        # Count unique responses
        if response_id not in seen_response_ids:
            stats['total_responses'] += 1
            seen_response_ids.add(response_id)
            
            # Location
            if row['location']:
                stats['locations'][row['location']] += 1
            
            # Overall satisfaction
            if row['overall_satisfaction'] is not None:
                stats['overall_satisfaction'][row['overall_satisfaction']] += 1
        
        # Question data
        if row['question_id'] and row['question_text']:
            question_text = row['question_text']
            original_text = row['original_text'] or question_text
            
            # Check if this is a free text question (based on question_type or content)
            is_free_text = False
            if row['question_type'] == 'free_text':
                is_free_text = True
            elif any(keyword in original_text.lower() for keyword in ['предложения', 'предложение', 'какие дополнительные', 'покрывают ваши потребности']):
                is_free_text = True
            
            if is_free_text:
                # Free text questions - collect all non-empty responses
                if row['answer_text'] and str(row['answer_text']).strip():
                    stats['free_text_questions'][original_text].append(row['answer_text'])
            else:
                # Rating/multiple choice questions
                question_key = original_text
                
                # Handle questions with sub-questions (text after "/")
                if "/" in question_text:
                    main_q, sub_q = question_text.split("/", 1)
                    main_q = main_q.strip()
                    sub_q = sub_q.strip()
                    
                    # Use original text for main question
                    if "/" in original_text:
                        orig_main, orig_sub = original_text.split("/", 1)
                        main_q_key = orig_main.strip()
                        sub_q_key = orig_sub.strip()
                    else:
                        main_q_key = question_key
                        sub_q_key = sub_q
                    
                    stats['questions'][main_q_key]['total'] += 1
                    
                    if row['rating_value'] is not None:
                        answer_key = f"{row['rating_value']} - {row['answer_text']}" if row['answer_text'] else str(row['rating_value'])
                        stats['questions'][main_q_key]['sub_questions'][sub_q_key]['answers'][answer_key] += 1
                        stats['questions'][main_q_key]['sub_questions'][sub_q_key]['total'] += 1
                    elif row['answer_text']:
                        stats['questions'][main_q_key]['sub_questions'][sub_q_key]['answers'][row['answer_text']] += 1
                        stats['questions'][main_q_key]['sub_questions'][sub_q_key]['total'] += 1
                else:
                    # Simple question without sub-question
                    stats['questions'][question_key]['total'] += 1
                    
                    if row['rating_value'] is not None:
                        answer_key = f"{row['rating_value']} - {row['answer_text']}" if row['answer_text'] else str(row['rating_value'])
                        stats['questions'][question_key]['answers'][answer_key] += 1
                    elif row['answer_text']:
                        stats['questions'][question_key]['answers'][row['answer_text']] += 1
    
    # Add all locations (even those with 0 responses)
    all_locations = get_all_locations()
    for loc in all_locations:
        if loc not in stats['locations']:
            stats['locations'][loc] = 0
    
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
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    
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
    
    # Questions data with proper formatting
    questions_data = []
    for q_text, q_data in stats['questions'].items():
        if q_data['total'] > 0:
            # Check if this question has sub-questions
            if q_data['sub_questions']:
                # Sort sub-questions
                sub_questions_sorted = sorted(q_data['sub_questions'].items(), 
                                             key=lambda x: sum(x[1]['answers'].values()), 
                                             reverse=True)
                
                for sub_q_text, sub_q_data in sub_questions_sorted:
                    if sub_q_data['total'] > 0:
                        # Sort answers by count
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
    satisfaction_sorted = sorted(stats['overall_satisfaction'].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
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
                'responses': responses[:10],  # Show only first 10 responses
                'has_more': len(responses) > 10
            })
    
    # Problem frequency data
    problem_data = []
    for q_text, q_data in stats['questions'].items():
        if "проблемами вы сталкиваетесь" in q_text.lower() or "problems" in q_text.lower():
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
    
    return render_template('dashboard.html',
                         total_responses=total_responses,
                         location_data=location_data,
                         questions_data=questions_data,
                         satisfaction_data=satisfaction_data,
                         free_text_data=free_text_data,
                         problem_data=problem_data,
                         charts=charts)

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics."""
    stats = get_survey_statistics()
    return jsonify(stats)

@app.route('/api/export/csv')
def export_csv():
    """Export all data as CSV."""
    rows = get_all_responses()
    
    # Convert to DataFrame
    data = []
    for row in rows:
        data.append({
            'response_id': row['response_id'],
            'location': row['location'],
            'overall_satisfaction': row['overall_satisfaction'],
            'question': row['original_text'] or row['question_text'],
            'answer': row['answer_text'],
            'rating': row['rating_value']
        })
    
    df = pd.DataFrame(data)
    
    # Save to CSV
    csv_path = 'survey_export.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    return send_file(csv_path, as_attachment=True, download_name='survey_results.csv')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
