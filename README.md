# LabelCheck

**Smart India Hackathon 2026 | Problem Statement SIH26034**

LabelCheck AI is a web-based inspection assistant that helps Legal Metrology inspectors check packaged commodity labels faster and in a structured way.

> **Hackathon prototype:** The extraction and detection pipeline is implemented. The complete category-based Legal Metrology compliance/rule engine is the next major development stage. The system is an inspection assistant and does not make legally binding decisions.

## Current Workflow

```text
Product Label Image(s)
        ↓
Camera / Upload
        ↓
OpenCV Preprocessing
        ↓
OCR.space + Gemini Vision
        ↓
Structured Label Fields
        ↓
Detected / Needs Verification / Not Found
        ↓
Inspector Review
```

### Planned Complete Workflow

```text
Images
  ↓
OCR + Vision
  ↓
Field Extraction
  ↓
Product Category
  ↓
Applicable Rules
  ↓
Compliance Engine
  ↓
Violations + Rule References
  ↓
Inspection Report
```

## Current Features

- Product label image upload
- Camera capture
- Multiple images for one inspection
- OpenCV preprocessing
- OCR.space text extraction
- Gemini multimodal visual extraction
- Structured field extraction
- Human-verification status for unclear fields
- OCR fallback if Gemini is unavailable
- Responsive inspection-oriented web UI

## Fields Extracted

- Product name
- Product category
- MRP
- Net quantity
- Manufacturing date
- Expiry / Best Before
- Batch number
- Manufacturer
- Packer
- Importer
- Consumer care details
- Country of origin
- Unit sale price
- FSSAI licence number for applicable food products

FSSAI is treated separately because it belongs to the food-regulatory domain and is not a universal Legal Metrology requirement.

## Detection Status

We deliberately do not use arbitrary numerical confidence scores.

- **Detected:** clearly readable and associated with the field
- **Needs Verification:** ambiguous, partially readable, or difficult to associate
- **Not Found:** no usable information detected

The inspector remains the final decision-maker.

## Technology Stack

**Frontend**
- HTML
- CSS
- JavaScript

**Backend**
- Python
- Flask

**Image Processing**
- OpenCV
- NumPy

**OCR**
- OCR.space API

**AI / Vision**
- Google Gemini API
- `google-genai`
- Pydantic structured output

**Configuration**
- python-dotenv
- Environment variables

## How Extraction Works

### OCR

OpenCV prepares the image before sending it to OCR by resizing, converting to grayscale, improving contrast and reducing noise.

OCR.space then extracts the visible text.

### Gemini Vision

Gemini receives the product images together with the OCR text.

The image is the primary evidence because package labels often use visual layouts that plain OCR can lose.

Gemini can use the visual relationship between labels and values to understand the package more reliably.

The model is instructed not to invent information. Unclear information is marked **Needs Verification** instead.

## Compliance Engine

The compliance engine is the main next stage.

It will compare extracted fields against the rules applicable to the detected product category.

Example:

```text
Extracted Information
MRP          → ₹99
Net Quantity → 100 ml
Batch No.    → TAPF027
Consumer Care → Not Found

             ↓

Applicable Rules
             ↓
Compliance Check
             ↓

✓ MRP detected
✓ Net quantity detected
✓ Batch number detected
✗ Consumer care declaration missing
```

The final system will show the reason/evidence for a flagged item and the relevant rule reference.

The rule database will be updateable so regulatory changes can be handled without rewriting the whole application.

## Human-in-the-Loop

Label inspection can involve unclear images, product-specific requirements and regulatory interpretation.

So LabelCheck AI is designed as an **inspection assistant**, not an autonomous legal decision-maker.

1. Extract information
2. Apply defined checks
3. Highlight possible issues
4. Show supporting evidence
5. Inspector makes the final decision

## Running Locally

### 1. Clone

```bash
git clone <YOUR_REPOSITORY_URL>
cd LabelCheck-AI
```

### 2. Create virtual environment

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

```env
OCR_API_KEY=your_ocr_space_key
GEMINI_API_KEY=your_gemini_key
FLASK_SECRET_KEY=your_secret_key
```

**Never commit `.env` or API keys to GitHub.**

### 5. Run

```bash
python app.py
```

Open `http://127.0.0.1:5000`

## Project Structure

```text
LabelCheck-AI/
│
├── app.py
├── gemini_extractor.py
├── text_processor.py
├── requirements.txt
├── .env
├── .gitignore
│
├── templates/
│   └── index.html
│
└── static/
    └── ...
```

## Limitations

- Blurry, tilted or tiny text can affect OCR/vision extraction.
- Some fields may require human verification.
- Cloud OCR/AI services have API limits and require internet access.
- Different product categories can have different applicable requirements.
- The complete Legal Metrology compliance engine is still being developed.
- Results are decision support, not legally binding judgements.

## Future Development

- Category-based Legal Metrology rule database
- Compliance engine and violation detection
- Rule references and explanations
- Font-size and readability checks
- Multilingual labels
- Barcode/product identification
- Inspection history and dashboard
- PDF inspection reports
- Offline/on-device OCR options
- Government-system integration

## Project Goal

The goal is not to replace an inspector.

It is to reduce the repetitive work of reading labels, finding declarations and checking them one by one.

**Scan → Extract → Verify → Detect → Report**

**Team:** Recursive Minds  
**Hackathon:** Smart India Hackathon 2026  
**Problem Statement:** SIH26034
