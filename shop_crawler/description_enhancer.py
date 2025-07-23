import os
import glob
import pandas as pd
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from difflib import get_close_matches

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google Sheets setup
SHEET_ID = "1YJDjmEu_RPvy4DDJoLA7ZO-4lgGtLSUCo1obJp7lFlI"
SHEET_NAME = "Sheet2"
GOOGLE_KEY_FILE = os.getenv("GOOGLE_KEY_PATH")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_KEY_FILE, scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
brand_data = sheet.get_all_records()
brand_map = {row['Brand Name'].strip().lower(): row['Brand URL'].strip() for row in brand_data}

TIER1_CSV = "tier1_products.csv"
TIER2_CSV = "tier2_products.csv"

SYSTEM_PROMPT = "You are a helpful assistant for rewriting e-commerce product descriptions in Polish."

# Helpers
def clean_html(text: str) -> str:
    # Remove Markdown code fences like ```html
    text = re.sub(r"^```html\s*|```$", "", text.strip(), flags=re.IGNORECASE)

    # Convert Markdown-style bold/italic to HTML if GPT missed it
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

    # Convert headings starting with #, ##, ### to <h2>
    text = re.sub(r"^#{1,3}\s*(.*?)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)

    # Strip any empty paragraphs or non-breaking space paragraphs
    text = re.sub(r"<p[^>]*>(&nbsp;|\s)*</p>", "", text, flags=re.IGNORECASE)

    # Replace multiple <br> with just one, and remove any leading ones
    text = re.sub(r"(<br\s*/?>\s*)+", "<br>", text, flags=re.IGNORECASE)
    text = re.sub(r"^(<br\s*/?>)+", "", text, flags=re.IGNORECASE)

    # Remove list indicators (1., 2., etc.) if not wrapped in <ol>/<ul>
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)

    # Final cleanup: remove whitespace at the top
    return text.strip()

def wrap_standalone_lines(text: str) -> str:
    lines = text.splitlines()
    wrapped = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Wrap if it's not already valid HTML
        if not line.startswith("<") and not line.endswith(">"):
            wrapped.append(f"<p>{line}</p>")
        else:
            wrapped.append(line)
    return "\n".join(wrapped)


def wrap_table_scroll(html: str) -> str:
    return re.sub(r"(<table.*?>.*?</table>)", r'<div style="overflow-x:auto;">\\1</div>', html, flags=re.DOTALL)

# Load .env and initialize client
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INPUT_CSV = "products.csv"
OUTPUT_CSV = "products_enhanced.csv"

def enhance_with_gpt(system_prompt: str, user_prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        print(f"GPT error: {e}")
        return ""

def match_brand(scraped_name: str, brand_list: list) -> str:
    scraped = str(scraped_name).strip().lower()
    match = get_close_matches(scraped, brand_list, n=1, cutoff=0.6)
    return match[0] if match else ""

# Main Enhancement Pipeline
tier1_rows, tier2_rows = [], []

for file_path in glob.glob("missing.csv"):
    print(f"Processing: {file_path}")
    df = pd.read_csv(file_path, encoding="utf-8-sig")

    if "Title" not in df.columns or "Nutrition Facts" not in df.columns:
        print(f"Skipping {file_path} due to missing columns.")
        continue

    # Fix brand
    brand_list = list(brand_map.keys())
    for i, row in df.iterrows():
        scraped_brand = str(row.get("Brand", "")).strip()
        corrected = match_brand(scraped_brand, brand_list)
        if corrected:
            df.at[i, "Brand"] = corrected.title()

    df["Enhanced Short Description"] = ""
    df["Enhanced Long Description"] = ""
    df["Focus Keyword"] = ""


    for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"Enhancing {file_path}"):
        name = str(row["Title"]).strip()

        # Generate focus keyword
        keyword_prompt = f"""
        You are an SEO assistant. Suggest the best focus keyword (in Polish) for the following product title:
        "{name}"

        Rules:
        - Return only the keyword
        - Do NOT use quotes or markdown
        - Must be in Polish
        - Avoid repeating the brand name unless necessary
        """

        focus_keyword = enhance_with_gpt(SYSTEM_PROMPT, keyword_prompt).strip()
        df.at[idx, "Focus Keyword"] = focus_keyword

        nutrition = str(row["Nutrition Facts"]).strip()
        if not nutrition:
            tier2_rows.append(row)
            continue

        scraped_brand = str(row.get("Brand", "")).strip().lower()
        matched_brand = match_brand(scraped_brand, list(brand_map.keys()))
        brand_url = brand_map.get(matched_brand.lower(), "")
        brand = matched_brand 

        # Short description prompt
        short_prompt = f"""
Write a short SEO-optimized product description in Polish for: {name}
Use this focus keyword at the start: {focus_keyword}
Include: • Polish language • ~500 characters • HTML formatting • 3 SEO keywords
Use a clear, compliant tone suitable for e-commerce. Do not use markdown.
"""
        short = enhance_with_gpt(SYSTEM_PROMPT, short_prompt)
        df.at[idx, "Enhanced Short Description"] = short




        context = row.get("Long Description", "") or short

        # Long Description (3 sections + SEO + About Brand)
        section_prompts = [
            f"""
You are an expert SEO copywriter. Use the following context and write the first section in minimum 250 words of a product description in HTML and in Polish for the product: {name}
Context: "{context}"
Include heading: <h2>Wprowadzenie</h2>
Describe what it is, who it is for, and its unique features.
Use focus keyword prominently and naturally.
""",
            f"""
Then write the second section (minimum 250 words) in Polish for the product: {name}
Include heading: <h2>Korzyści i zastosowanie</h2>
Explain benefits, ideal users (e.g., sport, keto), and usage instructions. Use proper HTML.
""",
            f"""
Now write the third section (minimum 250 words) in Polish for the product: {name}
Heading: <h2>Wartości odżywcze</h2>
Use this nutrition table for reference: "{nutrition}"
Add section: <h2>O marce {brand.title()}</h2> with 3 to 4 Polish sentences about the brand.
Add link as: <p>Więcej informacji znajdziesz na stronie producenta: <a href='{brand_url}' target='_blank'><strong><u>{brand_url}</u></strong></a></p>

"""
        ]

        sections = [enhance_with_gpt(SYSTEM_PROMPT, p) for p in section_prompts]
        combined_html = "\n".join(sections)
        cleaned_and_wrapped = wrap_standalone_lines(clean_html(combined_html))
        long_html = wrap_table_scroll(cleaned_and_wrapped)
        df.at[idx, "Enhanced Long Description"] = long_html

        # Add testing-only attributes
        df.at[idx, "Attribute 1 name"] = "Marki"
        df.at[idx, "Attribute 1 value(s)"] = row["Brand"]
        df.at[idx, "Attribute 2 name"] = "Kalorii"
        df.at[idx, "Attribute 2 value(s)"] = "301-500 Kalorii"
        df.at[idx, "Attribute 3 name"] = "Dieta"
        df.at[idx, "Attribute 3 value(s)"] = "Bez cukru"
        df.at[idx, "Published"] = -1

        tier1_rows.append(df.loc[idx])

# Save
if tier1_rows:
    df1 = pd.DataFrame(tier1_rows)
    df1.to_csv(TIER1_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved: {TIER1_CSV}")
if tier2_rows:
    df2 = pd.DataFrame(tier2_rows)
    df2.to_csv(TIER2_CSV, index=False, encoding="utf-8-sig")
    print(f"Skipped: {TIER2_CSV}")