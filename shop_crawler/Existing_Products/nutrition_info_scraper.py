#!/usr/bin/env python3
"""
nutrition_scraper.py  ────────────────────────────────────────────────────────────
Automatically fills the `NutritionHTML` column of a WooCommerce‑style CSV.

It works by:
1. Reading the source CSV (expects columns `Name` & `Attribute 1 value(s)` for brand).
2. Querying DuckDuckGo (or Google if you add an API) for the product + "wartości odżywcze".
3. Restricting results to known Polish fitness / keto shops (guiltfree.pl, noguiltmeal.pl,
   strefasupli.pl, sklepsport‑max.pl, oshee.eu, musclep… etc.).
4. Downloading the first matching product page (via requests).
5. Parsing the nutrition table or list with BeautifulSoup & regex.
6. Mapping the extracted nutrient values into your strict HTML template.
7. Writing a new CSV with the populated `NutritionHTML` column.

─────────────────────────────────────────────────────────────────────────────────
Install requirements:
    pip install pandas requests beautifulsoup4 duckduckgo_search tqdm unidecode

Run:
    python nutrition_scraper.py products_missing_nutrition.csv products_with_nutrition.csv

Tip: add the flag --headless if you enable Playwright for JS‑rendered sites.
"""

import re
import time
import argparse
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from tqdm import tqdm
from unidecode import unidecode

# ------------------------------ CONFIG --------------------------------------- #
ALLOWED_DOMAINS = [
    "guiltfree.pl",
    "noguiltmeal.pl",
    "okono.eu",
    "strefasupli.pl",
    "swiatsupli.pl",
    "sport-max.pl",
    "oshee.eu",
    "musclepower.pl",
    "bodypak.pl",
    "kfd.pl",
]

HTML_TEMPLATE = """
<div style='overflow-x:auto;'>
<h2>Tabela wartości odżywczych</h2>
<div style="overflow-x:auto;"><table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
<thead>
<tr style='background-color: #f2f2f2; text-align: left;'>
<th style='padding: 12px; border: 1px solid #ddd;'>Składnik</th>
<th style='padding: 12px; border: 1px solid #ddd;'>Wartość</th>
</tr>
</thead>
<tbody>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Wartość odżywcza</td><td style='padding: 12px; border: 1px solid #ddd;'>100 g</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Wartość energetyczna</td><td style='padding: 12px; border: 1px solid #ddd;'>{energy}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Tłuszcz</td><td style='padding: 12px; border: 1px solid #ddd;'>{fat}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>w tym kwasy tłuszczowe nasycone</td><td style='padding: 12px; border: 1px solid #ddd;'>{sat_fat}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Węglowodany</td><td style='padding: 12px; border: 1px solid #ddd;'>{carbs}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>w tym cukry</td><td style='padding: 12px; border: 1px solid #ddd;'>{sugars}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Białko</td><td style='padding: 12px; border: 1px solid #ddd;'>{protein}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Sól</td><td style='padding: 12px; border: 1px solid #ddd;'>{salt}</td></tr>
</tbody>
</table></div>
</div>
"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36",
}
REQUEST_TIMEOUT = 15  # seconds
# Delay between requests to be polite
REQUEST_DELAY = 2
# ----------------------------------------------------------------------------- #

def slugify(text: str) -> str:
    text = unidecode(text.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def search_product_page(query: str) -> Optional[str]:
    """Return the first product page URL that matches allowed domains."""
    with DDGS() as ddgs:
        results = ddgs.text(query, safesearch="off", max_results=10)
    for result in results:
        url = result["href"]
        for domain in ALLOWED_DOMAINS:
            if domain in url:
                return url
    return None


def fetch_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[warn] failed {url}: {e}")
        return None


def clean_text(cell: str) -> str:
    return re.sub(r"\s+", " ", cell).strip()


def extract_nutrition(soup: BeautifulSoup) -> Dict[str, str]:
    # Try to find <table> with energy etc.
    data = {}
    tables = soup.find_all("table")
    for tbl in tables:
        text = tbl.get_text("|", strip=True).lower()
        if any(k in text for k in ["wartość energetyczna", "energia", "tłuszcz"]):
            # Parse each row
            for row in tbl.find_all("tr"):
                cells = [clean_text(c.get_text()) for c in row.find_all(["th", "td"])]
                if len(cells) < 2:
                    continue
                key, val = cells[0].lower(), cells[1]
                if "wartość energetyczna" in key or "energia" in key:
                    data["energy"] = val
                elif key.startswith("tłuszcz") and "nasycone" not in key:
                    data["fat"] = val
                elif "nasycone" in key:
                    data["sat_fat"] = val
                elif key.startswith("węglowod") and "cukry" not in key:
                    data["carbs"] = val
                elif "cukry" in key:
                    data["sugars"] = val
                elif "białko" in key:
                    data["protein"] = val
                elif key.startswith("sól"):
                    data["salt"] = val
            if data:
                return data
    return {}


def format_html(nutrition: Dict[str, str]) -> str:
    default = {
        "energy": "—",
        "fat": "—",
        "sat_fat": "—",
        "carbs": "—",
        "sugars": "—",
        "protein": "—",
        "salt": "—",
    }
    merged = {**default, **nutrition}
    return HTML_TEMPLATE.format(**merged)


def process_product(name: str, brand: str) -> str:
    query = f"{brand} {name} wartości odżywcze"
    url = search_product_page(query)
    if not url:
        print(f"[skip] no url for {name}")
        return ""
    html = fetch_html(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    nutrition = extract_nutrition(soup)
    if not nutrition:
        print(f"[warn] nutrition parse failed for {url}")
    return format_html(nutrition)


def main(csv_in: str, csv_out: str, start: int = 0, limit: Optional[int] = None):
    df = pd.read_csv(csv_in)
    if "NutritionHTML" not in df.columns:
        df["NutritionHTML"] = ""
    rows = df.iloc[start: start + limit if limit else None]
    for idx, row in tqdm(rows.iterrows(), total=len(rows)):
        if pd.notna(row["NutritionHTML"]) and row["NutritionHTML"].strip():
            continue  # skip already filled
        html_block = process_product(row["Name"], row["Attribute 1 value(s)"])
        df.at[idx, "NutritionHTML"] = html_block
        time.sleep(REQUEST_DELAY)
    df.to_csv(csv_out, index=False)
    print(f"Saved → {csv_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill NutritionHTML column.")
    parser.add_argument("csv_in", help="Input CSV file")
    parser.add_argument("csv_out", help="Output CSV file")
    parser.add_argument("--start", type=int, default=0, help="Row to start from")
    parser.add_argument("--limit", type=int, default=None, help="Number of rows to process")
    args = parser.parse_args()

    main(args.csv_in, args.csv_out, args.start, args.limit)
