import os
from typing import Optional, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.7-flash"


class FieldResult(BaseModel):
    value: Optional[str] = Field(default=None, description="The value visibly present on the package, or null if unavailable.")
    status: Literal["detected", "needs_verification", "not_found"] = Field(description="detected when clearly readable and associated; needs_verification when ambiguous; not_found when no usable evidence exists.")
    evidence: Optional[str] = Field(default=None, description="Short description of the visible label evidence supporting the value.")


class LabelExtraction(BaseModel):
    product_name: FieldResult
    category: FieldResult
    mrp: FieldResult
    net_quantity: FieldResult
    manufacturing_date: FieldResult
    expiry_or_best_before: FieldResult
    batch_number: FieldResult
    manufacturer: FieldResult
    packer: FieldResult
    importer: FieldResult
    consumer_care: FieldResult
    country_of_origin: FieldResult
    unit_sale_price: FieldResult
    fssai_license_number: FieldResult


PROMPT = """You are the structured extraction engine for LabelCheck, a packaged-commodity inspection assistant.

Extract ONLY information visibly supported by the provided product label image(s). You are NOT deciding legal compliance.

The supplied images can be multiple views of the SAME product. Combine evidence across all views into one product record.

Use the images as PRIMARY evidence. Use OCR text as SUPPORTING evidence. OCR reading order may be wrong, so resolve label/value relationships using the actual visual layout.

Rules:
- Never invent, infer, or guess a value.
- status=detected only when the value is clearly readable and clearly associated with the field.
- status=needs_verification when some evidence exists but the value is ambiguous, blurry, partially readable, or cannot be reliably associated.
- status=not_found when no usable evidence exists in any supplied image.
- Do not mistake digits inside a batch/product code for MRP.
- Do not treat a sentence mentioning MRP as an actual MRP declaration.
- Preserve printed values and date formats where practical.
- MRP should contain the price only.
- Net quantity and unit sale price should include the visible unit.
- Manufacturer, packer, and importer may span multiple lines. Combine only when the image supports that association.
- Country of origin should only be extracted when explicitly stated, for example Made in India or Country of Origin: India.
- FSSAI licence number is food/beverage specific. Extract it only when clearly visible. For non-food products return not_found.
- Category should be a practical label category such as food, beverage, cosmetic, personal_care, household, packaged_goods, or unknown.
- Do not output legal compliance conclusions.

OCR TEXT:
"""


def extract_with_gemini(image_bytes_list, ocr_texts):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = PROMPT

    for i, text in enumerate(ocr_texts, start=1):
        prompt += f"\n--- IMAGE {i} OCR ---\n{text or '[No OCR text detected]'}\n"

    contents = [prompt]
    for image_bytes in image_bytes_list:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LabelExtraction,
                temperature=0
            )
        )
    except Exception as e:
        raise ValueError(f"Gemini service unavailable: {e}") from e

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    try:
        parsed = response.parsed
        if parsed is not None:
            return parsed.model_dump()
        return LabelExtraction.model_validate_json(response.text).model_dump()
    except Exception as e:
        raise ValueError(f"Could not parse Gemini response: {e}") from e
