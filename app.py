from flask import Flask, sessions, redirect, url_for, render_template, request
import requests
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

def extractText(image):
    payload = {'isOverlayRequired': 'false', 'apikey': os.getenv('OCR_API_KEY'), 'language': 'eng'}

    files = {'file': (image.filename, image.stream, image.mimetype)}

    r = requests.post(
        'https://api.ocr.space/parse/image', files=files, data=payload)
    return r.text

@app.route('/', methods=['GET', 'POST'])
def index():
    extracted_text = None
    if request.method == 'POST':
        image = request.files['image']
        if image:
            extracted_text = extractText(image)
            print(extracted_text)
        
    return render_template("index.html", extracted_text=extracted_text if request.method == 'POST' else None) 

if __name__ == '__main__':
    app.run(debug=True)
