import os
import cv2
import numpy as np
import requests
from text_processor import extract_fields, merge_field_results
from gemini_extractor import extract_with_gemini
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

OCR_API_KEY = os.getenv("OCR_API_KEY")


# ==================================================
# IMAGE PREPARATION
# ==================================================

def prepare_image(file_storage):
    image_bytes = file_storage.read()

    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not read the uploaded image.")

    return image


def prepare_for_gemini(image):
    height, width = image.shape[:2]
    max_dimension = 1800

    if max(height, width) > max_dimension:
        scale = max_dimension / max(height, width)
        width = int(width * scale)
        height = int(height * scale)
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

    success, encoded_image = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])

    if not success:
        raise ValueError("Could not prepare image for Gemini.")

    return encoded_image.tobytes()


def preprocess_for_ocr(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    max_dimension = 1800

    if max(height, width) > max_dimension:
        scale = max_dimension / max(height, width)
        width = int(width * scale)
        height = int(height * scale)
        gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    success, encoded_image = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 85])

    if not success:
        raise ValueError("Could not preprocess image for OCR.")

    return encoded_image.tobytes()


# ==================================================
# OCR
# ==================================================

def extract_text(processed_bytes, filename="processed.jpg"):
    if not OCR_API_KEY:
        raise ValueError("OCR_API_KEY is not configured.")

    payload = {"isOverlayRequired": "false", "apikey": OCR_API_KEY, "language": "eng"}
    files = {"file": (filename, processed_bytes, "image/jpeg")}

    try:
        response = requests.post("https://api.ocr.space/parse/image", files=files, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise ValueError(f"OCR service unavailable: {e}") from e
    except ValueError as e:
        raise ValueError("OCR service returned an invalid response.") from e

    if data.get("IsErroredOnProcessing"):
        raise ValueError(str(data.get("ErrorMessage", "OCR processing failed.")))

    parsed_results = data.get("ParsedResults", [])

    if not parsed_results:
        return ""

    text_parts = []

    for result in parsed_results:
        text = result.get("ParsedText", "")
        if text:
            text_parts.append(text)

    return "\n".join(text_parts)


# ==================================================
# MAIN ROUTE
# ==================================================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        images = request.files.getlist("images")
        images = [image for image in images if image and image.filename]

        if not images:
            return render_template("index.html", error="Please capture or select at least one image.")

        image_bytes_list = []
        ocr_texts = []
        fallback_fields = []
        results = []

        for image in images:
            try:
                decoded_image = prepare_image(image)
                gemini_bytes = prepare_for_gemini(decoded_image)
                ocr_bytes = preprocess_for_ocr(decoded_image)
                text = extract_text(ocr_bytes, image.filename)
                fields = extract_fields(text)

                image_bytes_list.append(gemini_bytes)
                ocr_texts.append(text)
                fallback_fields.append(fields)

                results.append({"filename": image.filename, "text": text, "fields": fields, "success": True})

            except Exception as e:
                results.append({"filename": image.filename, "text": "", "fields": {}, "success": False, "error": str(e)})

        merged_fields = {}
        extraction_source = None
        gemini_warning = None

        if image_bytes_list:
            try:
                merged_fields = extract_with_gemini(image_bytes_list, ocr_texts)
                extraction_source = "GEMINI + OCR"
            except Exception as e:
                merged_fields = merge_field_results(fallback_fields)
                extraction_source = "OCR FALLBACK"
                gemini_warning = str(e)
        else:
            merged_fields = merge_field_results(fallback_fields)
            extraction_source = "OCR FALLBACK"

        session["scan_results"] = results
        session["merged_fields"] = merged_fields
        session["extraction_source"] = extraction_source
        session["gemini_warning"] = gemini_warning

        return redirect(url_for("index"))

    results = session.pop("scan_results", None)
    merged_fields = session.pop("merged_fields", None)
    extraction_source = session.pop("extraction_source", None)
    gemini_warning = session.pop("gemini_warning", None)

    return render_template("index.html", results=results, merged_fields=merged_fields, extraction_source=extraction_source, gemini_warning=gemini_warning)


if __name__ == "__main__":
    app.run(debug=True)
