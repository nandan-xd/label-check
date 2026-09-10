import re
from collections import Counter


# ==================================================
# CLEANING
# ==================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = text.replace("—", "-").replace("–", "-")
    text = text.replace("|", " ")

    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def normalize_ocr_text(text):
    text = clean_text(text)
    text = re.sub(r"\bM\.?\s*R\.?\s*P\.?\b", "MRP", text, flags=re.I)
    text = re.sub(r"\bR\.?\s*S\.?\b", "Rs", text, flags=re.I)
    text = re.sub(r"\bF\.?\s*S\.?\s*S\.?\s*A\.?\s*I\.?\b", "FSSAI", text, flags=re.I)
    return text


# ==================================================
# RESULT FORMAT
# ==================================================

def make_result(value=None, status="not_found", source=None):
    return {
        "value": value,
        "status": status,
        "source": source
    }


# ==================================================
# HELPERS
# ==================================================

def clean_candidate(value):
    value = re.sub(r"\s+", " ", value).strip(" :;,-.")
    return value


def normalize_for_compare(value, field=None):
    """Loose normalization used only to decide whether two extracted values
    should be treated as 'the same' when voting across multiple images.

    Numeric fields (price, unit price) are compared by their numeric value
    so that "40" and "40.00" are recognised as agreeing, rather than by
    raw string equality.
    """
    if value is None:
        return ""

    if field in ("mrp",):
        number = to_float(value)
        if number is not None:
            return f"n:{number:.2f}"

    if field == "unit_sale_price":
        match = re.match(r"([\d.]+)\s*/?\s*([a-zA-Z]*)", value)
        if match:
            number = to_float(match.group(1))
            unit = match.group(2).lower()
            if number is not None:
                return f"n:{number:.2f}:{unit}"

    if field == "net_quantity":
        match = re.match(r"([\d.]+)\s*([a-zA-Z]*)", value)
        if match:
            number = to_float(match.group(1))
            unit = match.group(2).lower()
            if number is not None:
                return f"n:{number:.3f}:{unit}"

    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def is_label_line(line):
    patterns = [
        r"\bmrp\b",
        r"maximum\s+retail\s+price",
        r"net\s+(qty|quantity|weight|wt|volume|vol)",
        r"\bbatch\b",
        r"\blot\b",
        r"mfg\.?",
        r"manufactur",
        r"use\s+before",
        r"best\s+before",
        r"expiry|exp\.?",
        r"consumer\s+care",
        r"customer\s+care",
        r"contact\s+us",
        r"country\s+of\s+origin",
        r"made\s+in",
        r"packed\s+(by|for)",
        r"imported\s+by",
        r"marketed\s+by",
        r"\busp\b",
        r"unit\s+sale\s+price",
        r"fssai",
        r"lic(?:ense|ence)?\s*no"
    ]

    return any(re.search(pattern, line, re.I) for pattern in patterns)


def to_float(value):
    """Convert a numeric-looking OCR token to a float, correcting a small
    set of digit/letter confusions that only occur when the token is
    otherwise entirely numeric (avoids corrupting real alphabetic text)."""
    if value is None:
        return None

    value = value.strip()

    # Only apply letter->digit correction if the token is made up solely of
    # digits, separators, and the specific confusable letters. This keeps
    # us from mangling genuine words (e.g. addresses, names) elsewhere.
    if re.fullmatch(r"[0-9OoIlSs.,]+", value):
        value = re.sub(r"[Oo]", "0", value)
        value = re.sub(r"[Il]", "1", value)
        value = re.sub(r"[Ss]", "5", value)

    value = value.replace(",", ".")

    # Collapse an accidental double decimal point (e.g. "12..50") that can
    # result from noisy OCR.
    value = re.sub(r"\.(?=.*\.)", "", value)

    match = re.search(r"\d+(?:\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


# ==================================================
# DATE HANDLING
# ==================================================

_MONTHS = (
    r"(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|"
    r"JUL(?:Y)?|AUG(?:UST)?|SEP(?:T|TEMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
)

_DATE_PATTERNS = [
    rf"\b\d{{1,2}}[\s\-.]{_MONTHS}[\s\-.]\d{{2,4}}\b",          # 12-JAN-2025 / 12 JAN 2025
    rf"\b{_MONTHS}[\s\-.]\d{{1,2}}[,.]?\s*\d{{2,4}}\b",          # JAN 12, 2025
    rf"\b{_MONTHS}[\s\-.]\d{{2,4}}\b",                            # JAN 2025
    r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",                       # 12/01/2025
    r"\b\d{4}[/\-]\d{1,2}[/\-]\d{1,2}\b",                         # 2025-01-12
    r"\b\d{1,2}[/\-]\d{4}\b",                                     # 01/2025
    r"\b\d{4}[/\-]\d{1,2}\b",                                     # 2025/01
]

_DATE_RE = re.compile("|".join(f"(?:{p})" for p in _DATE_PATTERNS), re.I)


def find_date(text):
    match = _DATE_RE.search(text)
    if match:
        return match.group(0).strip()
    return None


# ==================================================
# FIELD LABELS
# ==================================================

FIELD_LABELS = {
    "mrp": [
        r"\bmrp\b",
        r"maximum\s+retail\s+price",
        r"max\.?\s+retail\s+price"
    ],
    "net_quantity": [
        r"net\s+(?:qty|quantity|weight|wt|volume|vol)",
        r"net\s*content",
        r"net\s*quantity"
    ],
    "manufacturing_date": [
        r"\bmfg\.?\s*(?:date|dt)?\b",
        r"\bmfd\.?\b",
        r"manufactur(?:ing|ed)?\s+date",
        r"date\s+of\s+manufactur",
        r"packaging\s+date",
        r"\bpkd\.?\b"
    ],
    "expiry_or_best_before": [
        r"use\s+before",
        r"best\s+before",
        r"use\s+by",
        r"expiry",
        r"exp\.?\s*date",
        r"\bexp\.?\b"
    ],
    "batch_number": [
        r"\bbatch\s*(?:no\.?|number)?",
        r"\blot\s*(?:no\.?|number)?"
    ],
    "manufacturer": [
        r"manufactured\s+by",
        r"manufacturer",
        r"manufactured\s*&?\s*marketed\s+by"
    ],
    "packer": [
        r"packed\s+by",
        r"packer",
        r"packed\s+for"
    ],
    "importer": [
        r"imported\s+by",
        r"importer"
    ],
    "consumer_care": [
        r"consumer\s+care",
        r"customer\s+care",
        r"consumer\s+helpline",
        r"customer\s+service",
        r"contact\s+us"
    ],
    "country_of_origin": [
        r"country\s+of\s+origin",
        r"made\s+in",
        r"manufactured\s+in"
    ],
    "unit_sale_price": [
        r"unit\s+sale\s+price",
        r"\busp\b"
    ],
    "fssai_license_number": [
        r"fssai\s*lic(?:ense|ence)?\s*(?:no\.?|number)?",
        r"fssai\s*(?:no\.?|number)?",
        r"lic(?:ense|ence)?\s*no\.?"
    ]
}

# A small allowlist keeps country-of-origin extraction honest: OCR noise
# after "Made in" / "Country of Origin" is common, so we prefer to only
# call it "detected" when it actually matches a recognizable country name.
_COMMON_COUNTRIES = {
    "india", "china", "usa", "united states", "united states of america",
    "uk", "united kingdom", "germany", "france", "italy", "japan", "korea",
    "south korea", "vietnam", "thailand", "malaysia", "indonesia", "taiwan",
    "singapore", "bangladesh", "sri lanka", "nepal", "pakistan", "uae",
    "united arab emirates", "australia", "canada", "mexico", "brazil",
    "switzerland", "netherlands", "spain", "turkey", "philippines"
}


# ==================================================
# DIRECT SAME-LINE EXTRACTION
# ==================================================

def extract_same_line(line, field):
    for label in FIELD_LABELS[field]:
        match = re.search(label, line, re.I)

        if not match:
            continue

        remainder = line[match.end():].strip(" :.-")

        # Don't let one field's value bleed into the next label on the same
        # line (e.g. "MRP Rs 100 Batch No AB123" grabbing "Batch No AB123").
        cutoff = None
        for other_field, other_patterns in FIELD_LABELS.items():
            if other_field == field:
                continue
            for other_label in other_patterns:
                other_match = re.search(other_label, remainder, re.I)
                if other_match and (cutoff is None or other_match.start() < cutoff):
                    cutoff = other_match.start()
        if cutoff is not None:
            remainder = remainder[:cutoff].strip(" :.-")

        if not remainder:
            continue

        if field == "mrp":
            value = re.search(r"(?:₹|Rs\.?|INR)?\s*([0-9OoIlSs]{1,6}(?:[.,][0-9OoIlSs]{1,2})?)", remainder, re.I)
            if value:
                number = to_float(value.group(1))
                if number is not None and 1 <= number <= 200000:
                    return value.group(1), "detected", line

        elif field == "net_quantity":
            value = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|ltr|litre|litres|liter|liters|pcs|pieces|units?|packs?)", remainder, re.I)
            if value:
                return f"{value.group(1)} {value.group(2)}", "detected", line

        elif field in ("manufacturing_date", "expiry_or_best_before"):
            value = find_date(remainder)
            if value:
                return value, "detected", line

        elif field == "batch_number":
            value = re.search(r"\b([A-Za-z0-9][A-Za-z0-9./_-]{2,})\b", remainder)
            if value and not re.fullmatch(r"\d+[/-]\d+", value.group(1)):
                return value.group(1), "detected", line

        elif field == "consumer_care":
            phone = re.search(r"(?:\+91[\s-]?)?\d{3,5}[\s-]?\d{3,5}[\s-]?\d{3,5}", remainder)
            email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", remainder)
            if phone:
                return phone.group(0), "detected", line
            if email:
                return email.group(0), "detected", line

        elif field == "country_of_origin":
            candidate = clean_candidate(re.split(r"[.,;]", remainder)[0])
            words = candidate.split()
            trimmed = " ".join(words[:4]) if len(words) > 4 else candidate
            if trimmed.lower() in _COMMON_COUNTRIES:
                return trimmed, "detected", line
            if re.fullmatch(r"[A-Za-z][A-Za-z ]{1,30}", trimmed):
                return trimmed, "needs_verification", line

        elif field == "unit_sale_price":
            value = re.search(r"(?:₹|Rs\.?|INR)?\s*([0-9OoIlSs]+(?:[.,][0-9OoIlSs]+)?)\s*(?:/|\bper\b)?\s*(kg|g|mg|ml|l)?", remainder, re.I)
            if value:
                number = to_float(value.group(1))
                if number is not None:
                    unit = value.group(2)
                    display = f"{number:.2f}/{unit.lower()}" if unit else f"{number:.2f}"
                    return display, "detected", line

        elif field == "fssai_license_number":
            value = re.search(r"\b\d{14}\b", remainder)
            if value:
                return value.group(0), "detected", line
            fallback = re.search(r"\b\d{8,14}\b", remainder)
            if fallback:
                return fallback.group(0), "needs_verification", line

        elif field in ("manufacturer", "packer", "importer"):
            return clean_candidate(remainder), "detected", line

    return None


# ==================================================
# NEARBY LINE EXTRACTION
# ==================================================

def extract_nearby(lines, field):
    for i, line in enumerate(lines):

        if not any(re.search(pattern, line, re.I) for pattern in FIELD_LABELS[field]):
            continue

        same_line = extract_same_line(line, field)

        if same_line:
            return same_line

        for distance in range(1, 4):
            j = i + distance

            if j >= len(lines):
                break

            candidate = lines[j].strip()

            if not candidate:
                continue

            if is_label_line(candidate):
                break

            if re.fullmatch(r"\(.*\)", candidate):
                continue

            if field == "mrp":
                match = re.fullmatch(r"(?:₹|Rs\.?|INR)?\s*([0-9OoIlSs]{1,6}(?:[.,][0-9OoIlSs]{1,2})?)", candidate, re.I)
                if match:
                    number = to_float(match.group(1))
                    if number and 1 <= number <= 200000:
                        return match.group(1), "detected", f"{line} → {candidate}"

            elif field == "net_quantity":
                match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|ltr|litre|litres|liter|liters|pcs|pieces|units?|packs?)", candidate, re.I)
                if match:
                    return f"{match.group(1)} {match.group(2)}", "detected", f"{line} → {candidate}"

            elif field in ("manufacturing_date", "expiry_or_best_before"):
                match = find_date(candidate)
                if match:
                    return match, "detected", f"{line} → {candidate}"

            elif field == "batch_number":
                if re.fullmatch(r"[A-Za-z0-9./_-]{3,}", candidate) and not re.fullmatch(r"\d+[/-]\d+", candidate):
                    return candidate, "detected", f"{line} → {candidate}"

            elif field == "consumer_care":
                phone = re.search(r"(?:\+91[\s-]?)?\d{3,5}[\s-]?\d{3,5}[\s-]?\d{3,5}", candidate)
                email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", candidate)
                if phone:
                    return phone.group(0), "detected", f"{line} → {candidate}"
                if email:
                    return email.group(0), "detected", f"{line} → {candidate}"

            elif field in ("manufacturer", "packer", "importer"):
                return clean_candidate(candidate), "detected", f"{line} → {candidate}"

            elif field == "country_of_origin":
                trimmed = clean_candidate(candidate)
                words = trimmed.split()
                trimmed = " ".join(words[:4]) if len(words) > 4 else trimmed
                if trimmed.lower() in _COMMON_COUNTRIES:
                    return trimmed, "detected", f"{line} → {candidate}"
                if re.fullmatch(r"[A-Za-z][A-Za-z ]{1,30}", trimmed):
                    return trimmed, "needs_verification", f"{line} → {candidate}"

            elif field == "unit_sale_price":
                match = re.search(r"([0-9OoIlSs]+(?:[.,][0-9OoIlSs]+)?)\s*(?:/|\bper\b)?\s*(kg|g|mg|ml|l)?", candidate, re.I)
                if match:
                    number = to_float(match.group(1))
                    if number is not None:
                        unit = match.group(2)
                        display = f"{number:.2f}/{unit.lower()}" if unit else f"{number:.2f}"
                        return display, "detected", f"{line} → {candidate}"

            elif field == "fssai_license_number":
                match = re.search(r"\b\d{14}\b", candidate)
                if match:
                    return match.group(0), "detected", f"{line} → {candidate}"

    return None


# ==================================================
# FREE TEXT FIELDS
# ==================================================

def extract_free_text(lines, field):
    patterns = FIELD_LABELS[field]

    for i, line in enumerate(lines):

        for pattern in patterns:
            match = re.search(pattern, line, re.I)

            if not match:
                continue

            remainder = line[match.end():].strip(" :.-")

            if remainder:
                return clean_candidate(remainder), "detected", line

            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()

                if not candidate or is_label_line(candidate):
                    continue

                return clean_candidate(candidate), "detected", f"{line} → {candidate}"

    return None


# ==================================================
# COUNTRY (whole-text fallback pass)
# ==================================================

def extract_country(text):
    for pattern in (
        r"country\s+of\s+origin\s*:?\s*([A-Za-z][A-Za-z ]+)",
        r"made\s+in\s*:?\s*([A-Za-z][A-Za-z ]+)"
    ):
        match = re.search(pattern, text, re.I)
        if not match:
            continue

        candidate = clean_candidate(re.split(r"[.,;\n]", match.group(1))[0])
        words = candidate.split()
        candidate = " ".join(words[:4]) if len(words) > 4 else candidate

        status = "detected" if candidate.lower() in _COMMON_COUNTRIES else "needs_verification"
        return candidate, status, match.group(0)

    return None


# ==================================================
# PRODUCT NAME
# ==================================================

def extract_product_name(lines):
    ignored = [
        r"mrp", r"net", r"batch", r"mfg", r"manufactur",
        r"use\s+before", r"best\s+before", r"expiry",
        r"ingredients", r"consumer", r"customer", r"contact",
        r"made\s+in", r"country\s+of\s+origin", r"fssai",
        r"for\s+external\s+use", r"caution", r"warning",
        r"www\.", r"@", r"usp", r"retail\s+price", r"lic(?:ense|ence)?\s*no"
    ]

    for line in lines:

        if len(line) < 2:
            continue

        if any(re.search(pattern, line, re.I) for pattern in ignored):
            continue

        if re.fullmatch(r"[\d\s./,:;+\-]+", line):
            continue

        if re.fullmatch(r"\(.*\)", line):
            continue

        words = line.split()

        if len(words) <= 8 and not re.search(r"\d{3,}", line):
            return clean_candidate(line), "needs_verification", line

    return None


# ==================================================
# MAIN EXTRACTION
# ==================================================

def extract_fields(text, lines_data=None):
    text = normalize_ocr_text(text)
    lines = text.splitlines()

    result = {}

    for field in FIELD_LABELS:
        found = extract_nearby(lines, field)

        if found:
            result[field] = make_result(found[0], found[1], found[2])
        else:
            result[field] = make_result()

    manufacturer = extract_free_text(lines, "manufacturer")
    if manufacturer:
        result["manufacturer"] = make_result(manufacturer[0], manufacturer[1], manufacturer[2])

    packer = extract_free_text(lines, "packer")
    if packer:
        result["packer"] = make_result(packer[0], packer[1], packer[2])

    importer = extract_free_text(lines, "importer")
    if importer:
        result["importer"] = make_result(importer[0], importer[1], importer[2])

    consumer = extract_free_text(lines, "consumer_care")
    if consumer:
        result["consumer_care"] = make_result(consumer[0], consumer[1], consumer[2])

    # Only let the whole-text country fallback override a "not_found"/lower
    # confidence nearby-line result, and never downgrade a detected value.
    country = extract_country(text)
    if country and result["country_of_origin"].get("status") != "detected":
        result["country_of_origin"] = make_result(country[0], country[1], country[2])

    product_name = extract_product_name(lines)
    if product_name:
        result["product_name"] = make_result(product_name[0], product_name[1], product_name[2])
    else:
        result["product_name"] = make_result()

    return result


# ==================================================
# MERGE MULTIPLE IMAGES
# ==================================================

def merge_field_results(results):
    """Combine per-image OCR extractions into one record per field.

    When several images agree on the same value, confidence goes up
    (still "detected"). When images disagree, we surface the most common
    reading but flag it as "needs_verification" rather than silently
    picking whichever image happened to be processed first.
    """
    if not results:
        return {}

    fields = set()
    for result_set in results:
        fields.update(result_set.keys())

    merged = {}

    for field in fields:
        detected = [
            r.get(field) for r in results
            if r.get(field) and r[field].get("value") and r[field].get("status") == "detected"
        ]

        if detected:
            counts = Counter(normalize_for_compare(item["value"], field) for item in detected)
            best_key, best_count = counts.most_common(1)[0]
            candidates_for_best = [
                item for item in detected
                if normalize_for_compare(item["value"], field) == best_key
            ]
            chosen = candidates_for_best[0]

            if len(counts) == 1:
                merged[field] = make_result(chosen["value"], "detected", chosen.get("source"))
            else:
                # Conflicting readings across images - keep the most frequent
                # value but ask a human to double check it.
                merged[field] = make_result(chosen["value"], "needs_verification", chosen.get("source"))
            continue

        verification = [
            r.get(field) for r in results
            if r.get(field) and r[field].get("value")
        ]

        if verification:
            merged[field] = verification[0]
        else:
            merged[field] = make_result()

    return merged