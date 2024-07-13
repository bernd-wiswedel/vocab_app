from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pandas as pd
import random
import json
import os
from fetch_data import fetch_data, COL_NAME_TERM, COL_NAME_COMMENT, COL_NAME_TRANSLATION, COL_NAME_CATEGORY, COL_NAME_LANGUAGE

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

# Load data from public Google Sheets
vocab_data = fetch_data()

@app.route('/')
def index():
    languages = ['Latein', 'Englisch']
    return render_template('index.html', languages=languages)

@app.route('/get_categories')
def get_categories():
    language = request.args.get('language')
    if language:
        categories = list(set(str(item[COL_NAME_CATEGORY]) for item in vocab_data if item[COL_NAME_LANGUAGE] == language and pd.notna(item[COL_NAME_CATEGORY])))
    else:
        categories = []
    return jsonify(categories=categories)

@app.route('/reload_data', methods=['POST'])
def reload_data():
    global vocab_data
    vocab_data = fetch_data()
    return redirect(url_for('index'))

@app.route('/practice', methods=['POST'])
def practice():
    selected_language = request.form['language']
    selected_categories = request.form['categories'].split(',')

    filtered_data = [item for item in vocab_data if item[COL_NAME_CATEGORY] in selected_categories and item[COL_NAME_LANGUAGE] == selected_language]

    return render_template(
        'practice.html',
        vocab_data=filtered_data,
        language=selected_language,
        col_name_term=COL_NAME_TERM,
        col_name_comment=COL_NAME_COMMENT,
        col_name_translation=COL_NAME_TRANSLATION
    )

@app.route('/test', methods=['POST'])
def test():
    selected_language = request.form['language']
    selected_categories = request.form['categories'].split(',')

    filtered_data = [item for item in vocab_data if item[COL_NAME_CATEGORY] in selected_categories and item[COL_NAME_LANGUAGE] == selected_language]
    session['test_data'] = filtered_data
    session['correct_answers'] = 0
    session['wrong_answers'] = 0

    return redirect(url_for('testing'))

@app.route('/testing')
def testing():
    if not session.get('test_data'):
        return redirect(url_for('index'))

    current_data = random.choice(session['test_data'])
    return render_template('test.html',
                           current_data=current_data,
                           term_key=COL_NAME_TERM,
                           comment_key=COL_NAME_COMMENT,
                           translation_key=COL_NAME_TRANSLATION,
                           correct_count=session['correct_answers'],
                           wrong_count=session['wrong_answers'],
                           show_translation=False)

@app.route('/show_translation', methods=['POST'])
def show_translation():
    current_data = json.loads(request.form['current_data'])  # Convert JSON string back to dictionary
    return render_template('test.html',
                           current_data=current_data,
                           term_key=COL_NAME_TERM,
                           comment_key=COL_NAME_COMMENT,
                           translation_key=COL_NAME_TRANSLATION,
                           correct_count=session['correct_answers'],
                           wrong_count=session['wrong_answers'],
                           show_translation=True)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    answer_correct = request.form['answer_correct'] == 'Richtig'
    if answer_correct:
        session['correct_answers'] += 1
    else:
        session['wrong_answers'] += 1

    return redirect(url_for('testing'))

@app.route('/result')
def result():
    return render_template('result.html', correct=session['correct_answers'], wrong=session['wrong_answers'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
