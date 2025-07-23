# Updated script to enforce RankMath rules strictly and generate SEO Title + Meta Description

import pandas as pd
import os
import re
import time
import random
import requests
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime

# === LOAD ENV ===
load_dotenv()
print("Loaded GROK_API_KEY:", repr(os.getenv("GROK_API_KEY")))
GROK_API_KEY = os.getenv("GROK_API_KEY")

# === SETTINGS ===
INPUT_CSV = "export_for_reference.csv"
OUTPUT_CSV = "export_for_reference_enhanced.csv"
BATCH_SIZE = 300
SYSTEM_PROMPT = "You are a helpful assistant for rewriting e-commerce product descriptions in Polish."

MANUAL_START_INDEX = 0  # Set to None to auto-detect from existing output
if os.path.exists(OUTPUT_CSV):
    done_df = pd.read_csv(OUTPUT_CSV)
    auto_start_index = len(done_df)
    START_INDEX = MANUAL_START_INDEX if MANUAL_START_INDEX is not None else auto_start_index
else:
    START_INDEX = MANUAL_START_INDEX if MANUAL_START_INDEX is not None else 0

# === LOAD BRAND MAPPING ===
brand_url_map = (
    pd.read_csv("mapped_brands.csv", encoding="utf-8-sig")  # ensure BOM stripped
      .set_index("Brand Name")["Brand URL"]
      .to_dict()
)
brand_url_map = {
    k.strip().lower(): v.strip() for k, v in brand_url_map.items()
}

# === HTML HELPERS ===
def clean_html(text: str) -> str:
    text = re.sub(r"^```html\s*|```$", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    text = re.sub(r"^#{1,3}\s*(.*?)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"<p[^>]*>(&nbsp;|\s)*</p>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(<br\s*/?>\s*)+", "<br>", text, flags=re.IGNORECASE)
    text = re.sub(r"^(<br\s*/?>)+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    return text.strip()

def wrap_standalone_lines(text):
    lines = text.splitlines()
    wrapped = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not line.startswith("<") and not line.endswith(">"):
            wrapped.append(f"<p>{line}</p>")
        else:
            wrapped.append(line)
    return "\n".join(wrapped)

def wrap_table_scroll(html):
    return re.sub(r"(<table.*?>.*?</table>)", r'<div style="overflow-x:auto;">\1</div>', html, flags=re.DOTALL)

def log_issue(name, message):
    with open("enhancement_failures.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {name} – {message}\n")


def extract_nutrition_from_context(text):
    match = re.search(r'(Wartości odżywcze[\s\S]+?)(?:<h2>|</h2>|$)', text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if len(content) < 30 or not any(x in content.lower() for x in ["kcal", "białko", "tłuszcz", "węglowodany"]):
            return None
        return content
    return None

# === GROK CALL ===
def enhance_with_grok(system_prompt, user_prompt):
    import requests
    import os
    import time
    import random

    GROK_API_KEY = os.getenv("GROK_API_KEY")  # Should be the xAI key now

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "grok-3-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }

    retry_delay = 30
    for attempt in range(5):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                return clean_html(response.json()["choices"][0]["message"]["content"])
            elif response.status_code == 429:
                wait = retry_delay + random.randint(0, 10)
                print(f"⏳ Rate limited. Waiting {wait}s (Attempt {attempt+1}/5)...")
                time.sleep(wait)
                retry_delay *= 2
            elif response.status_code == 401:
                print(f"❌ Invalid Grok API key.")
                print(response.json())
                return ""
            else:
                print(f"❌ GROK error {response.status_code}: {response.text}")
                return ""
        except Exception as e:
            print(f"❌ Request error: {e}")
            return ""
    print("❌ Max retries reached. Skipping.")
    return ""



# === MAIN ===
df_input = pd.read_csv(INPUT_CSV)
df_output = pd.read_csv(OUTPUT_CSV) if os.path.exists(OUTPUT_CSV) else pd.DataFrame()
processed_names = set(df_output["Name"]) if "Name" in df_output.columns else set()
batch = df_input[~df_input["Name"].isin(processed_names)].head(BATCH_SIZE).copy()
if batch.empty:
    print("✅ All products are already enhanced.")
    exit()

# Keep a running "done" DF that we will append to and save:
df_done = df_output.copy()

for col in ["Enhanced Short Description", "Enhanced Long Description",
            "Meta: rank_math_focus_keyword", "Meta: seo_title", "Meta: seo_description"]:
    if col not in batch.columns:
        batch[col] = ""

# QUICK WIN #3: process in sub-batches
CHUNK_SIZE = 10

for start in range(0, len(batch), CHUNK_SIZE):
    sub_batch = batch.iloc[start : start + CHUNK_SIZE].copy()

    # 1) Process each row in the chunk
    for idx, row in tqdm(
        sub_batch.iterrows(),
        total=len(sub_batch),
        desc=f"Enhancing products {start+1}-{min(start+CHUNK_SIZE, len(batch))}"
    ):
        name = str(row["Name"]).strip()
        context = str(row.get("Description", "")).strip()
        nutrition = extract_nutrition_from_context(context)
        original_short = str(row.get("Short Description", "")).strip() or "Brak opisu."

        # === Focus Keyword ===
        keyword_prompt = f"""
You are an SEO assistant. Suggest the best focus keyword (in Polish) for the product:
"{name}"
Return only the keyword (no quotes or markdown).
"""
        focus_keyword = enhance_with_grok(SYSTEM_PROMPT, keyword_prompt).strip()
        sub_batch.at[idx, "Meta: rank_math_focus_keyword"] = focus_keyword

        # === SEO Title ===
        seo_title = f"{focus_keyword} - {name} | NoGuiltMeal"
        sub_batch.at[idx, "Meta: seo_title"] = seo_title

        # === Meta Description ===
        meta_prompt = f"""
Generate a short meta description in Polish (max 160 characters) for the product below.
Make sure to include the exact phrase: {focus_keyword}

Product title: {name}
Short description: {original_short}
"""
        seo_meta_desc = enhance_with_grok(SYSTEM_PROMPT, meta_prompt)
        seo_meta_desc = seo_meta_desc.strip()
        if len(seo_meta_desc) > 160:
            seo_meta_desc = seo_meta_desc[:157].rstrip() + "..."

        sub_batch.at[idx, "Meta: seo_description"] = seo_meta_desc

        # === Short Description ===
        short_prompt = f"""
Write a short product description in Polish in at least 500 characters using HTML.
Include the exact focus keyword: {focus_keyword} at the beginning.
Original short description for context: {original_short}
Avoid using markdown.
"""
        short_desc = enhance_with_grok(SYSTEM_PROMPT, short_prompt)
        sub_batch.at[idx, "Enhanced Short Description"] = short_desc

        if not nutrition:
            print(f"⚠️ No nutrition data found for: {name}")
            nutrition = "Brak danych o wartościach odżywczych."

        brand = str(row.get("Attribute 1 value(s)", "")).strip()
        brand_url = brand_url_map.get(brand.lower())

        # === Long Description in 4 Sections ===
        section_prompts = [
            f"""
Write Section 1 of a long product description in Polish using HTML.

<h2>Wprowadzenie</h2>

Write at least 250 words for product: {name}.

Start with a paragraph that includes the exact focus keyword: "{focus_keyword}" in the first sentence. Use <p> tags for each paragraph. Do not use markdown.
""",
            f"""
Write Section 2 of the product description in Polish using HTML.

<h2>Korzyści i zastosowanie</h2>

Write at least 250 words about the benefits and use cases of the product: {name}.

Use proper <p> tags. Avoid markdown.
""",
            f"""
Write Section 3 of the product description in Polish using HTML.

<h2>Wartości odżywcze</h2>

Write a minimum 250-word summary of the product’s nutritional benefits based on the following data:
"{nutrition}"

Use <p> tags for each paragraph. Do not create a table here.
Do not use markdown.
""",
            f"""
Write Section 4 of the product description in Polish using only HTML.

<h2>Tabela wartości odżywczych</h2>

Based on this data: "{nutrition}", generate a valid HTML table with 2 columns:
- Składnik
- Wartość

Wrap the table inside this container:
<div style='overflow-x:auto;'> ... </div>

Use proper tags: <table>, <thead>, <tbody>, <tr>, <th>, <td>
Do not use markdown or placeholders like \\1.
Make sure the table displays cleanly in a browser.
""" + (
                f"""

<h2>O marce {brand.title()}</h2>
Write 3–4 sentences in Polish introducing the brand.

<p>Więcej informacji znajdziesz na stronie producenta: <a href='{brand_url}' target='_blank'><strong><u>{brand_url}</u></strong></a></p>
""" if brand_url else ""
            )
        ]

        sections = []
        for i, prompt in enumerate(section_prompts):
            section = enhance_with_grok(SYSTEM_PROMPT, prompt)
            if not section:
                print(f"⚠️ GROK failed to generate Section {i+1} for: {name}")
            elif len(section.split()) < 220:
                print(f"⚠️ Section {i+1} may be too short ({len(section.split())} words) for: {name}")
            sections.append(section)

        full_html = wrap_table_scroll(wrap_standalone_lines("\n".join(sections)))
        sub_batch.at[idx, "Enhanced Long Description"] = full_html

    # 2) After finishing all rows in this chunk, append & save
    df_done = pd.concat([df_done, sub_batch], ignore_index=True)
    df_done.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"✅ Saved progress up through products {start+1}-{start+len(sub_batch)} to {OUTPUT_CSV}")

    # 3) Short break before next chunk
    print(f"-- Finished chunk {start+1}–{start+len(sub_batch)}, sleeping…")
    time.sleep(60)

print("✅ All chunks completed! You can now find the enhanced descriptions in", OUTPUT_CSV)
