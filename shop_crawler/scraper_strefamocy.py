# --- sportmax updated to match strefamocy structure ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time
import random
import re
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=10, help="Number of products per category")
parser.add_argument('--headless', action='store_true', help="Run browser in headless mode")
args = parser.parse_args()

CATEGORY_URLS = [
    "https://sklep.sport-max.pl/odzywki-bialkowe/?filter_producer=1335778696,1321975103,1320788286",
    "https://sklep.sport-max.pl/kreatyny/?filter_producer=1335778696,1321975103,1320788286",
    "https://sklep.sport-max.pl/boostery-testosteronu/?filter_producer=1335778696,1321975103",
    "https://sklep.sport-max.pl/tribulus/?filter_producer=1335778696",
    "https://sklep.sport-max.pl/aminokwasy-hmb/",
    "https://sklep.sport-max.pl/glutamina/?filter_producer=1335778696,1321975103",
    "https://sklep.sport-max.pl/aminokwasy-bcaa/?filter_producer=1335778696,1321975103,1320788286",
]

CATEGORY_NAMES = {
    CATEGORY_URLS[0]: "Błka",
    CATEGORY_URLS[1]: "Kreatyna",
    CATEGORY_URLS[2]: "Boostery testosteronu",
    CATEGORY_URLS[3]: "Tribulus",
    CATEGORY_URLS[4]: "Aminokwasy HMB",
    CATEGORY_URLS[5]: "Aminokwasy Glutamina",
    CATEGORY_URLS[6]: "Aminokwasy BCAA",
}

CATEGORY_STRUCTURE = {
    "Błka": "Odżywki > Białka",
    "Kreatyna": "Odżywki > Kreatyna",
    "Boostery testosteronu": "Boostery Testosteronu > Boostery Testosteronu",
    "Tribulus": "Boostery Testosteronu > Tribulus",
    "Aminokwasy HMB": "Aminokwasy > Aminokwasy HMB",
    "Aminokwasy Glutamina": "Aminokwasy > Aminokwasy Glutamina",
    "Aminokwasy BCAA": "Aminokwasy > Aminokwasy BCAA",
}

PRODUCTS_PER_CATEGORY = args.count
HEADLESS = args.headless

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def extract_dieta_attribute(desc_text):
    desc_text = desc_text.lower()
    dieta_map = {
        "no added sugar": "No added sugar",
        "sugar free": "Sugar free",
        "gluten free": "Gluten free",
        "lactose free": "Lactose free",
        "keto": "Keto",
        "low carb": "Low carb",
        "vegan": "Vegan",
        "high protein": "High protein",
        "plant based": "Plant based",
    }
    terms = {pl for en, pl in dieta_map.items() if en in desc_text}
    return ", ".join(sorted(terms))

def extract_kalorii_attribute(nutrition_text):
    patterns = [
        r'(\d+[\.,]?\d*)\s*kcal.*?100\s*g',
        r'100\s*g.*?(\d+[\.,]?\d*)\s*kcal',
    ]
    for pattern in patterns:
        match = re.search(pattern, nutrition_text, re.IGNORECASE)
        if match:
            cal_str = match.group(1).replace(",", ".")
            try:
                cal = float(cal_str)
                if cal < 300:
                    return "Below 300 calories"
                elif cal <= 500:
                    return "301-500 calories"
                elif cal <= 1000:
                    return "501-1000 calories"
                else:
                    return "Over 1000 calories"
            except:
                return ""
    return ""

def fetch_product_data(driver):
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1.product_name__name").text.strip()
    except:
        return None

    try:
        short_desc = driver.find_element(By.CSS_SELECTOR, "div.product_name__block.--description").text.strip()
    except:
        short_desc = ""

    try:
        long_desc = driver.find_element(By.ID, "projector_longdescription").text.strip()
    except:
        long_desc = ""

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li.menu__bar--table"))).click()
        time.sleep(1.5)
    except:
        pass

    nutrition_facts = []
    try:
        table_html = driver.find_element(By.ID, "tabelka6").get_attribute("outerHTML")
        soup = BeautifulSoup(table_html, "html.parser")
        for row in soup.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                nutrition_facts.append(f"{cols[0].text.strip()}: {cols[1].text.strip()} (100g)")
    except:
        pass

    nutrition_flat = "; ".join(nutrition_facts)

    try:
        gtin = ""
        brand = ""
        rows = driver.find_elements(By.CSS_SELECTOR, ".product-data-table tr")
        for row in rows:
            th = row.find_element(By.TAG_NAME, "th").text.strip()
            td = row.find_element(By.TAG_NAME, "td").text.strip()
            if "EAN" in th:
                gtin = td
            if "Producent" in th:
                brand = td
    except:
        gtin = ""
        brand = ""

    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "a.photos__link img.photos__photo")
        image_urls = [img.get_attribute("src") for img in imgs if img.get_attribute("src")]
    except:
        image_urls = []

    dieta_val = extract_dieta_attribute(short_desc + " " + long_desc)
    kalorii_val = extract_kalorii_attribute(nutrition_flat)

    return {
        "Name": title,
        "Short description": short_desc,
        "Description": long_desc,
        "GTIN, UPC, EAN, or ISBN": gtin,
        "Brands": brand,
        "Categories": CATEGORY_STRUCTURE.get(category_name, category_name),
        "Images": ",".join(image_urls),
        "Regular price": "",
        "Attribute 1 name": "Dieta",
        "Attribute 1 value(s)": dieta_val,
        "Attribute 1 visible": 1,
        "Attribute 1 global": 1,
        "Attribute 2 name": "Kalorii",
        "Attribute 2 value(s)": kalorii_val,
        "Attribute 2 visible": 1,
        "Attribute 2 global": 1,
        "Attribute 3 name": "Marki",
        "Attribute 3 value(s)": brand,
        "Attribute 3 visible": 1,
        "Attribute 3 global": 1,
    }

# --- WebDriver Setup ---
options = webdriver.ChromeOptions()
options.add_argument("--window-size=1920,1080")
if HEADLESS:
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

results = []

for category_url in CATEGORY_URLS:
    category_name = CATEGORY_NAMES.get(category_url, "")
    print(f"\n🔍 Scraping category: {category_name} ({category_url})")

    driver.get(category_url)
    time.sleep(2)

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.acceptAll"))).click()
    except:
        pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    for _ in range(10):
        driver.execute_script("window.scrollBy(0,500)")
        time.sleep(1)

    product_urls = []
    cards = driver.find_elements(By.XPATH, "//a[contains(@class, 'product__name')]")
    for card in cards:
        try:
            link = card.get_attribute("href")
            if link and link not in product_urls:
                product_urls.append(link)
            if len(product_urls) >= PRODUCTS_PER_CATEGORY * 2:
                break
        except:
            continue

    scraped_titles = set()
    added_count = 0

    for url in product_urls:
        if added_count >= PRODUCTS_PER_CATEGORY:
            break

        driver.get(url)
        random_sleep(3, 6)
        data = fetch_product_data(driver)

        if not data:
            print("⚠️ Skipped due to error, retrying...")
            time.sleep(2)
            driver.get(url)
            random_sleep(2, 4)
            data = fetch_product_data(driver)

        if data:
            title = data.get("Name", "").strip()
            if title in scraped_titles:
                print(f"⏩ Duplicate skipped: {title}")
                continue

            scraped_titles.add(title)
            results.append(data)
            added_count += 1
            print(f"✅ Product added: {title}")
        else:
            print("❌ Skipped after retry")

driver.quit()

if results:
    fieldnames = list(results[0].keys())
    with open("products_sportmax.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print("📦 Scraping complete — products_sportmax.csv saved")
else:
    print("⚠️ No data scraped.")
