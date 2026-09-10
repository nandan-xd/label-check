import re


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
    return re.sub(r"\s+", " ", value).strip(" :;,-.")


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
        r"unit\s+sale\s+price"
    ]

    return any(re.search(pattern, line, re.I) for pattern in patterns)


def to_float(value):
    if value is None:
        return None

    value = value.strip()
    value = re.sub(r"(?<=\d)[Oo](?=\d)", "0", value)
    value = re.sub(r"(?<=\d)[Il](?=\d)", "1", value)
    value = re.sub(r"(?<=\d)[Ss](?=\d)", "5", value)
    value = value.replace(",", ".")

    match = re.search(r"\d+(?:\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
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
        r"date\s+of\s+manufactur"
    ],
    "expiry_or_best_before": [
        r"use\s+before",
        r"best\s+before",
        r"use\s+by",
        r"expiry",
        r"exp\.?\s*date"
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
    ]
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

        if not remainder:
            continue

        if field == "mrp":
            value = re.search(r"(?:₹|Rs\.?|INR)?\s*([0-9OoIlSs]{1,6}(?:[.,][0-9OoIlSs]{1,2})?)", remainder, re.I)

            if value and 1 <= to_float(value.group(1)) <= 200000:
                return value.group(1), "detected", line

        elif field == "net_quantity":
            value = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|ltr|litre|litres|liter|liters)", remainder, re.I)

            if value:
                return f"{value.group(1)} {value.group(2)}", "detected", line

        elif field in ("manufacturing_date", "expiry_or_best_before"):
            value = re.search(r"\b(\d{1,2}[/-]\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}(?:[/-]\d{1,2})?)\b", remainder)

            if value:
                return value.group(1), "detected", line

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
            value = re.search(r"[A-Za-z][A-Za-z ]{2,}", remainder)

            if value:
                return clean_candidate(value.group(0)), "detected", line

        elif field == "unit_sale_price":
            value = re.search(r"(?:₹|Rs\.?|INR)?\s*([0-9OoIlSs]+(?:[.,][0-9OoIlSs]+)?)\s*(?:/|\bper\b)?\s*(kg|g|mg|ml|l)?", remainder, re.I)

            if value:
                number = to_float(value.group(1))

                if number is not None:
                    unit = value.group(2)
                    display = f"{number:.2f}/{unit.lower()}" if unit else f"{number:.2f}"
                    return display, "detected", line

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
                match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|ltr|litre|litres|liter|liters)", candidate, re.I)

                if match:
                    return f"{match.group(1)} {match.group(2)}", "detected", f"{line} → {candidate}"

            elif field in ("manufacturing_date", "expiry_or_best_before"):
                match = re.search(r"\b(\d{1,2}[/-]\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}(?:[/-]\d{1,2})?)\b", candidate)

                if match:
                    return match.group(1), "detected", f"{line} → {candidate}"

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
                match = re.search(r"[A-Za-z][A-Za-z ]{2,}", candidate)

                if match:
                    return clean_candidate(match.group(0)), "detected", f"{line} → {candidate}"

            elif field == "unit_sale_price":
                match = re.search(r"([0-9OoIlSs]+(?:[.,][0-9OoIlSs]+)?)\s*(?:/|\bper\b)?\s*(kg|g|mg|ml|l)?", candidate, re.I)

                if match:
                    number = to_float(match.group(1))

                    if number is not None:
                        unit = match.group(2)
                        display = f"{number:.2f}/{unit.lower()}" if unit else f"{number:.2f}"
                        return display, "detected", f"{line} → {candidate}"

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
# COUNTRY
# ==================================================

def extract_country(text):
    match = re.search(r"country\s+of\s+origin\s*:?\s*([A-Za-z][A-Za-z ]+)", text, re.I)

    if match:
        return clean_candidate(match.group(1)), "detected", match.group(0)

    match = re.search(r"made\s+in\s*:?\s*([A-Za-z][A-Za-z ]+)", text, re.I)

    if match:
        return clean_candidate(match.group(1)), "detected", match.group(0)

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
        r"www\.", r"@", r"usp", r"retail\s+price"
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

    country = extract_country(text)

    if country:
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
    if not results:
        return {}

    fields = set()

    for result_set in results:
        fields.update(result_set.keys())

    merged = {}

    for field in fields:
        detected = []

        for result_set in results:
            item = result_set.get(field)

            if item and item.get("value"):
                if item.get("status") == "detected":
                    detected.append(item)

        if detected:
            merged[field] = detected[0]
            continue

        verification = []

        for result_set in results:
            item = result_set.get(field)

            if item and item.get("value"):
                verification.append(item)

        if verification:
            merged[field] = verification[0]
        else:
            merged[field] = make_result()

    return merged