import pandas as pd
from app import LegalRule, app, db

df = pd.read_excel("D:/label check stuff/legal_rules.xlsx", sheet_name="Core Rules")

with app.app_context():
    for _, row in df.iterrows():
        rule = LegalRule(
            product_category=row["Product Category"],
            field=row["Field"],
            requirement=row["Requirement / Condition"],
            requirement_type=row["Mandatory / Conditional"],
            exception_condition=row["Exception / Condition"],
            applicable_section=row["Rule / Section No."],
            engine_check=row["Compliance Engine Check"],
            source_notes=row["Source / Notes"]
        )
        db.session.add(rule)

    db.session.commit()