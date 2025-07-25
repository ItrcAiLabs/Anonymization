from flask import Flask, render_template, request, redirect, url_for
import json
import os

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from processor import CourtCaseProcessor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    headers = None
    records = None
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            return redirect(request.url)
        filename = file.filename.lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        if filename.endswith('.txt'):
            processor = CourtCaseProcessor(filepath)
            processor.read_and_extract()
            df = processor.parse_cases()
            records = df.to_dict(orient='records')
        elif filename.endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                records = json.load(f)
        else:
            return redirect(request.url)

        if records:
            # ensure list of dicts
            headers = list(records[0].keys())
    return render_template('index.html', headers=headers, records=records)

if __name__ == '__main__':
    app.run(debug=True)