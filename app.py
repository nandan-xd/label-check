from flask import Flask, render_template, request
import requests
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class LegalRule(db.Model):
    __tablename__ = "legal_rules"
    rule_id = db.Column(db.Integer, primary_key=True)
    product_category = db.Column(db.String(100))
    field = db.Column(db.String(100))
    requirement = db.Column(db.Text)
    requirement_type = db.Column(db.String(50))
    exception_condition = db.Column(db.Text)
    applicable_section = db.Column(db.String(100))
    engine_check = db.Column(db.String(100))
    source_notes = db.Column(db.Text)

with app.app_context():
    db.create_all()

def extract_text(image):
    payload = {"apikey": os.getenv("OCR_API_KEY"), "language": "eng", "isOverlayRequired": "false"}

    files = {"file": (image.filename, image.stream, image.content_type)}

    response = requests.post("https://api.ocr.space/parse/image", files=files, data=payload)
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        return "OCR failed"
    parsed_results = result.get("ParsedResults")
    if not parsed_results:
        return "No text detected."
    return parsed_results[0]["ParsedText"]

def get_rules():
    rules = LegalRule.query.all()
    return rules

def process_text(ocr_text):
    pass

def check_compliance(product_data, rules):
    pass
    
@app.route("/", methods=["GET", "POST"])
def index():
    extracted_text = None
    processed_text = None
    rules = get_rules()
    if request.method == "POST":
        image = request.files.get("image")
        if image and image.filename:
            extracted_text = extract_text(image)
            processed_text = process_text(extracted_text)
    return render_template("index.html", extracted_text=extracted_text, processed_text=processed_text)

if __name__ == "__main__":
    app.run(debug=True)