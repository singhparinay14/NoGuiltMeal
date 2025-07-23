import pandas as pd
import re

INPUT_FILE = "export_for_reference_enhanced.csv"
OUTPUT_FILE = "products_missing_nutrition.csv"

# Common Polish no-data phrases
NO_DATA_PHRASES = [
    "brak danych",
    "nie posiadamy szczegółowych danych",
    "informacje niedostępne",
    "n/a",
]

def is_table_empty_or_fake(html):
    if "<table" not in html.lower():
        return True  # No table at all

    # Check for meaningful table rows
    data_cells = re.findall(r"<td[^>]*>(.*?)</td>", html, re.IGNORECASE | re.DOTALL)
    cleaned_cells = [re.sub("<.*?>", "", cell).strip().lower() for cell in data_cells]
    meaningful_cells = [cell for cell in cleaned_cells if cell and all(phrase not in cell for phrase in NO_DATA_PHRASES)]

    return len(meaningful_cells) == 0

# Load CSV
df = pd.read_csv(INPUT_FILE)
missing_rows = []

for idx, row in df.iterrows():
    desc = str(row.get("Enhanced Long Description", ""))
    if is_table_empty_or_fake(desc):
        missing_rows.append(row)

# Save output
if missing_rows:
    pd.DataFrame(missing_rows).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Saved {len(missing_rows)} products without valid nutrition tables to {OUTPUT_FILE}")
else:
    print("✅ All products have valid nutrition tables.")
