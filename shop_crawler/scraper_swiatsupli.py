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
    "https://swiatsupli.pl/odzywki-bialkowe/c146?producenci=biotechusa,olimp-sport-nutrition,optimum-nutrition,trec-nutrition",
    "https://swiatsupli.pl/kreatyny/c179?producenci=biotechusa,olimp-sport-nutrition,trec-nutrition&page=2",
    "https://swiatsupli.pl/boostery-testosteronu/c184",
    "https://swiatsupli.pl/tribulus/c170?producenci=biotechusa,olimp-sport-nutrition",
    "https://swiatsupli.pl/hmb/c166?producenci=olimp-sport-nutrition",
    "https://swiatsupli.pl/glutaminy/c164?producenci=biotechusa,olimp-sport-nutrition,trec-nutrition",
    "https://swiatsupli.pl/bcaa/c131?producenci=biotechusa,olimp-sport-nutrition,optimum-nutrition,trec-nutrition&page=2",
]

CATEGORY_NAMES = {
    CATEGORY_URLS[0]: "Białka",
    CATEGORY_URLS[1]: "Kreatyna",
    CATEGORY_URLS[2]: "Boostery testosteronu",
    CATEGORY_URLS[3]: "Tribulus",
    CATEGORY_URLS[4]: "Aminokwasy HMB",
    CATEGORY_URLS[5]: "Aminokwasy Glutamina",
    CATEGORY_URLS[6]: "Aminokwasy BCAA",
}

CATEGORY_STRUCTURE = {
    "Białka": "Odżywki > Białka",
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
    data = {}

    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1.product_name").text.strip()
    except:
        title = ""

    data["Title"] = title
    data["Short Description"] = title

    # --- Click the Szczegóły produktu tab before parsing ---
    try:
        tab_button = driver.find_element(By.CSS_SELECTOR, "a.nav-link[href='#product-details']")
        tab_button.click()
        time.sleep(1.5)
    except:
        pass

    # --- Long Description ---
    try:
        long_desc_html = driver.find_element(By.CSS_SELECTOR, "div.product-description").get_attribute("outerHTML")
        soup = BeautifulSoup(long_desc_html, "html.parser")
        data["Long Description"] = soup.get_text("\n", strip=True)
    except:
        data["Long Description"] = ""

    # --- Nutrition Facts ---
    nutrition_facts = []
    try:
        details_div = driver.find_element(By.ID, "product-details")
        table_html = details_div.find_element(By.TAG_NAME, "table").get_attribute("outerHTML")
        soup = BeautifulSoup(table_html, "html.parser")
        for row in soup.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) > 4:
                label = cols[0].get_text(strip=True)
                value = cols[4].get_text(strip=True)
                nutrition_facts.append(f"{label}: {value} (100g)")
    except:
        pass
    nutrition_flat = "; ".join(nutrition_facts)

    # --- GTIN ---
    try:
        gtin_elem = driver.find_element(By.CSS_SELECTOR, "div.product-reference span[itemprop='sku']")
        gtin = gtin_elem.get_attribute("textContent").strip()
    except:
        gtin = ""

    # --- Brand ---
    try:
        brand = driver.find_element(By.CSS_SELECTOR, "div.pl_manufacturer a strong").text.strip()
    except:
        brand = ""

    # --- Price ---
    try:
        price = driver.find_element(By.CSS_SELECTOR, "div.current-price span.price").text.strip()
    except:
        price = ""

    # --- Main Image ---
    try:
        main_img = driver.find_element(By.CSS_SELECTOR, "div.product-cover img").get_attribute("src")
    except:
        main_img = ""

    # --- Gallery Images ---
    gallery_urls = []
    try:
        thumbs = driver.find_elements(By.CSS_SELECTOR, "ul.product-images img")
        for img in thumbs:
            src = img.get_attribute("data-image-large-src") or img.get_attribute("src")
            if src and src not in gallery_urls:
                gallery_urls.append(src)
    except:
        pass

    data["images"] = main_img
    data["product_image_gallery"] = ",".join(gallery_urls)

    dieta_val = extract_dieta_attribute(data["Long Description"])
    kalorii_val = extract_kalorii_attribute(nutrition_flat)

    data = {
        "Name": title,
        "Short description": title,  # Or use a real short description if you extract one
        "Description": data.get("Long Description", ""),
        "GTIN, UPC, EAN, or ISBN": gtin,
        "Brands": brand,
        "Categories": CATEGORY_STRUCTURE.get(category_name, category_name),
        "Images": ",".join([main_img] + gallery_urls),
        "Regular price": price,
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

    return data

# --- Setup WebDriver ---
options = webdriver.ChromeOptions()
options.add_argument("--window-size=1920,1080")
if HEADLESS:
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")  # Optional for Windows compatibility

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

results = []

for category_url in CATEGORY_URLS:
    category_name = CATEGORY_NAMES.get(category_url, "")
    print(f"\n🔍 Scraping category: {category_name} ({category_url})")

    driver.get(category_url)
    time.sleep(2)

    try:
        cookie_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "submit-btn1"))
        )
        cookie_button.click()
        print("✅ Cookie button clicked")
    except:
        print("⚠️ Cookie button not found or already accepted")

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    for _ in range(10):
        driver.execute_script("window.scrollBy(0,500)")
        time.sleep(1)

    product_urls = []
    cards = driver.find_elements(By.CSS_SELECTOR, "article.product-miniature")
    print(f"🔍 Found {len(cards)} product links")

    for card in cards:
        try:
            link = card.find_element(By.CSS_SELECTOR, "h3.product-title a").get_attribute("href")
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
            title = data.get("Title", "").strip()
            if title in scraped_titles:
                print(f"⏩ Duplicate skipped: {title}")
                continue

            scraped_titles.add(title)
            added_count += 1
            data["Categories"] = CATEGORY_STRUCTURE.get(category_name, category_name)
            results.append(data)
            print(f"✅ Product added: {title}")
        else:
            print("❌ Skipped after retry")

driver.quit()

# --- Save CSV ---
if results:
    fieldnames = list(results[0].keys())
    with open("products_swiatsupli.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print("📦 Scraping complete — products_swiatsupli.csv saved")
else:
    print("⚠️ No data scraped.")

