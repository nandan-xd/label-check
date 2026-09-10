import os
import time
from typing import Optional, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

try:
    from google.genai.errors import ClientError, ServerError
except ImportError:  # pragma: no cover - older/newer SDK versions
    class ClientError(Exception):
        pass

    class ServerError(Exception):
        pass

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")

# Keep retries limited and cheap: label images are small and a couple of
# retries is enough to ride out transient 429/5xx errors without making the
# user wait too long on a genuinely broken request.
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5
REQUEST_TIMEOUT_MS = 45_000


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


PROMPT = """You are a SECONDARY visual extraction engine for LabelCheck. OCR is the PRIMARY text extraction system. Your job is not to replace OCR. Use the images to recover information OCR may have missed and to help resolve visual label/value relationships.

Extract ONLY information visibly supported by the provided product label image(s). You are NOT deciding legal compliance.

Each API call is an independent inspection. Do not use, remember, or infer information from any previous scan. The supplied images can be multiple views of the SAME product. Combine evidence across all views into one product record.

Rules:
- Never invent, infer, or guess a value.
- Small text may be difficult to read. If it is not clearly readable, use needs_verification rather than guessing.
- OCR text is supporting evidence only. If OCR and the image disagree, trust what is visually legible in the image and lower the confidence to needs_verification rather than silently overriding OCR.
- status=detected only when the value is clearly readable and clearly associated with the field.
- status=needs_verification when some evidence exists but the value is ambiguous, blurry, partially readable, or cannot be reliably associated.
- status=not_found when no usable evidence exists in any supplied image.
- Do not mistake digits inside a batch/product code for MRP.
- Do not treat a sentence mentioning MRP as an actual MRP declaration.
- Preserve printed values and date formats where practical (do not reformat dates).
- MRP should contain the price only (no currency symbol, no "Incl. of taxes" text).
- Net quantity and unit sale price should include the visible unit.
- Manufacturer, packer, and importer may span multiple lines. Combine only when the image supports that association. Do not include unrelated address fragments from other fields (e.g. batch numbers, phone numbers) inside these values.
- Country of origin should only be extracted when explicitly stated, for example "Made in India" or "Country of Origin: India". A single recognizable country name only - do not include surrounding sentence text.
- FSSAI licence number is food/beverage specific and is a numeric code (commonly 14 digits). Extract it only when clearly visible. For non-food products return not_found.
- Category should be a practical label category such as food, beverage, cosmetic, personal_care, household, packaged_goods, or unknown.
- Do not output legal compliance conclusions.
- evidence should briefly describe WHERE on the label the value appears (e.g. "printed on bottom-left panel next to the batch code"), not just repeat the value.

OCR TEXT:
"""


def _build_contents(image_bytes_list, ocr_texts):
    prompt = PROMPT

    for i, text in enumerate(ocr_texts, start=1):
        prompt += f"\n--- IMAGE {i} OCR ---\n{text or '[No OCR text detected]'}\n"

    contents = [prompt]
    for image_bytes, mime_type in image_bytes_list:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    return contents


def _build_config():
    base_kwargs = dict(
        response_mime_type="application/json",
        response_schema=LabelExtraction,
        temperature=0,
    )
    try:
        return types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            **base_kwargs
        )
    except (TypeError, AttributeError):
        # Older/newer SDK versions may not expose http_options the same way -
        # degrade gracefully rather than crashing the whole request.
        return types.GenerateContentConfig(**base_kwargs)


def _call_gemini(client, contents):
    last_error = None
    config = _build_config()

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
        except ServerError as e:
            # 5xx errors are usually transient - worth a short retry.
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise ValueError(f"Gemini service unavailable after retries: {e}") from e
        except ClientError as e:
            # 4xx errors (bad key, bad request, quota) will not be fixed by
            # retrying, so fail fast with a clear message.
            raise ValueError(f"Gemini rejected the request: {e}") from e
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise ValueError(f"Gemini service unavailable: {e}") from e

    raise ValueError(f"Gemini service unavailable: {last_error}")


def extract_with_gemini(image_bytes_list, ocr_texts):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    if not image_bytes_list:
        raise ValueError("No images were provided for Gemini extraction.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    contents = _build_contents(image_bytes_list, ocr_texts)

    response = _call_gemini(client, contents)

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    try:
        parsed = response.parsed
        if parsed is not None:
            result = parsed.model_dump()
        else:
            result = LabelExtraction.model_validate_json(response.text).model_dump()
    except Exception as e:
        raise ValueError(f"Could not parse Gemini response: {e}") from e

    # Guard against a response that technically validates but is entirely
    # empty (every field not_found) - treat it the same as a parse failure
    # so the caller can fall back to OCR-only rather than silently trusting
    # a blank record.
    if all(field.get("status") == "not_found" for field in result.values()):
        raise ValueError("Gemini could not identify any label fields in the supplied images.")

    return result