# Scraper for GuiltFree.pl with updated fixes: remove blank rows, improve dieta parsing, ensure nutrition tab loads

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import random
import re
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=10, help="Number of products per category")
parser.add_argument('--headless', action='store_true', help="Run browser in headless mode")
args = parser.parse_args()

CATEGORY_URLS = [
    "https://guiltfree.pl/gb/354-high-protein-products",
    "https://guiltfree.pl/gb/355-protein-supplements?manufacturers=biotech-usa,olimp,optimum-nutrition",
    "https://guiltfree.pl/gb/639-sport-suplements",
    "https://guiltfree.pl/gb/393-healthy-sweets?categories=chocolate-without-sugar,chocolates-and-bonbons-without-sugar,cookies-without-sugar,wafers-without-sugar-and-light",
    "https://guiltfree.pl/gb/389-peanut-butters",
    "https://guiltfree.pl/gb/344-energy-drinks-without-sugar",
    "https://guiltfree.pl/gb/349-plant-based-drinks",
    "https://guiltfree.pl/gb/332-light-bread",
    "https://guiltfree.pl/gb/366-salty-light-snacks?categories=protein-chips,veggie-crisps",
    "https://guiltfree.pl/gb/380-ketchup-and-dressing?categories=dressings-zero-kcal,ketchup-without-sugar,light-mayonnaise,sauces-bbq-zero-kcal,zero-kcal-dips",
    "https://guiltfree.pl/gb/437-spices-without-salt",
]

CATEGORY_NAMES = {
    "https://guiltfree.pl/gb/354-high-protein-products": "Przekąski Proteinowe",
    "https://guiltfree.pl/gb/355-protein-supplements?manufacturers=biotech-usa,olimp,optimum-nutrition" : "Białka",
    "https://guiltfree.pl/gb/639-sport-suplements" : "Suplementy",
    "https://guiltfree.pl/gb/393-healthy-sweets?categories=chocolate-without-sugar,chocolates-and-bonbons-without-sugar,cookies-without-sugar,wafers-without-sugar-and-light" : "Przekąski",
    "https://guiltfree.pl/gb/389-peanut-butters" : "Smarowidła",
    "https://guiltfree.pl/gb/344-energy-drinks-without-sugar" : "Napoje Energetyczne",
    "https://guiltfree.pl/gb/349-plant-based-drinks" : "Szejki",
    "https://guiltfree.pl/gb/332-light-bread" : "Chleby",
    "https://guiltfree.pl/gb/366-salty-light-snacks?categories=protein-chips,veggie-crisps" : "Czipsy",
    "https://guiltfree.pl/gb/380-ketchup-and-dressing?categories=dressings-zero-kcal,ketchup-without-sugar,light-mayonnaise,sauces-bbq-zero-kcal,zero-kcal-dips" : "Sosy i Dipy",
    "https://guiltfree.pl/gb/437-spices-without-salt" : "Zioła i Przyprawy",
}

CATEGORY_STRUCTURE = {
    "Przekąski Proteinowe": "Przekąski > Przekąski Proteinowe",
    "Białka": "Odżywki > Białka",
    "Suplementy": "Odżywki > Suplementy",
    "Przekąski": "Słodycze > Przekąski",
    "Smarowidła": "Słodycze > Smarowidła",
    "Napoje Energetyczne": "Napoje > Napoje Energetyczne",
    "Szejki": "Napoje > Szejki",
    "Chleby": "Pieczywo > Chleby",
    "Czipsy": "Przekąski > Czipsy",
    "Sosy i Dipy": "Przyprawy > Sosy i Dipy",
    "Zioła i Przyprawy": "Przyprawy > Zioła i Przyprawy",
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
    # Try to extract calories per 100g with flexible patterns
    patterns = [
        r'Calories.*?\(100g\).*?([\d\.,]+)',
        r'Energy.*?([\d\.,]+)\s*kcal.*?100g',
        r'([\d\.,]+)\s*kcal\s*/\s*100g',
    ]
    for pattern in patterns:
        match = re.search(pattern, nutrition_text, re.IGNORECASE)
        if match:
            cal_str = match.group(1).replace(",", ".")
            try:
                cal = float(cal_str)
            except ValueError:
                return ""
            if cal < 300:
                return "Below 300 calories"
            if cal <= 500:
                return "301-500 calories"
            if cal <= 1000:
                return "501-1000 calories"
            return "Over 1000 calories"
    return ""

def fetch_product_data(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
        if not body_text or "Product not found" in body_text or "Page not available" in body_text:
            print("⚠️ Empty or broken product page — skipping")
            return None
    except:
        return None

    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1[itemprop='name']").text.strip()
    except:
        return None

    image_urls = []
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, ".images-container img.thumb.js-thumb")
        for img in imgs:
            src = img.get_attribute("data-image-large-src") or img.get_attribute("src")
            if src and src not in image_urls:
                image_urls.append(src.strip())
    except:
        pass

    try:
        brand = driver.find_element(By.CSS_SELECTOR, ".product-manufacturer span a").text.strip()
    except:
        brand = ""

    try:
        short_desc = driver.find_element(By.CSS_SELECTOR, "div[itemprop='description']").get_attribute("innerText").strip()
    except:
        short_desc = ""
    try:
        long_desc = driver.find_element(By.ID, "description").get_attribute("innerText").strip()
    except:
        long_desc = ""

    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//li[contains(., 'Nutritional values')]"))
        ).click()
        time.sleep(1.5)
    except:
        pass

    nutrition_facts = []
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "nutri_main_div")))
        rows = driver.find_elements(By.CSS_SELECTOR, ".nutri_main_div .row")
        for row in rows:
            try:
                label = row.find_element(By.CSS_SELECTOR, ".col-8_jp").text.strip()
                vals = row.find_elements(By.CSS_SELECTOR, ".col-2_jp")
                p1 = vals[0].text.strip() if len(vals) > 0 else ""
                p2 = vals[1].text.strip() if len(vals) > 1 else ""
                nutrition_facts.append(f"{label}: {p1} (portion), {p2} (100g)")
            except:
                continue
    except:
        pass

    nutrition_flat = "; ".join(nutrition_facts)

    try:
        label_img = driver.find_element(By.CSS_SELECTOR, ".product-attachments img").get_attribute("src").strip()
    except:
        label_img = ""

    dieta_val = extract_dieta_attribute(short_desc + " " + long_desc)
    kalorii_val = extract_kalorii_attribute(nutrition_flat)
    marki_val = brand

    gtin = ""
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            content = script.get_attribute("innerText")
            if '"@type": "Product"' in content and '"gtin13"' in content:
                try:
                    json_data = json.loads(content)
                    if isinstance(json_data, dict) and "gtin13" in json_data:
                        gtin = json_data["gtin13"]
                        break
                except json.JSONDecodeError:
                    continue
    except:
        pass

    return {
        "GTIN": gtin,
        "Title": title,
        "Price": "",
        "Brand": brand,
        "Short Description": short_desc,
        "Long Description": long_desc,
        "Nutrition Facts": nutrition_flat,
        "Nutrition Label URL": label_img,
        "images": ",".join(image_urls),
        "Attribute 1 name": "Dieta",
        "Attribute 1 value(s)": dieta_val,
        "Attribute 1 visible": 1,
        "Attribute 1 global": 1,
        "Attribute 2 name": "Kalorii",
        "Attribute 2 value(s)": kalorii_val,
        "Attribute 2 visible": 1,
        "Attribute 2 global": 1,
        "Attribute 3 name": "Marki",
        "Attribute 3 value(s)": marki_val,
        "Attribute 3 visible": 1,
        "Attribute 3 global": 1,
    }

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
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".x13eucookies__btn--accept-all"))
        )
        btn.click()
    except:
        pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    for _ in range(10):
        driver.execute_script("window.scrollBy(0,500)")
        time.sleep(1)

    product_urls = []
    cards = driver.find_elements(By.CSS_SELECTOR, "section#products article.product-miniature")
    print(f"🔍 Found {len(cards)} product cards on the page")

    for card in cards:
        try:
            if card.is_displayed():
                link = card.find_element(By.CSS_SELECTOR, "a.thumbnail").get_attribute("href")
                if link and "/gb/" in link:
                    print(f"🧲 Candidate product link: {link}")
                    product_urls.append(link)
            if len(product_urls) >= PRODUCTS_PER_CATEGORY:
                break
        except:
            continue

for category_url in CATEGORY_URLS:
    category_name = CATEGORY_NAMES.get(category_url, "")
    print(f"\n🔍 Scraping category: {category_name} ({category_url})")

    driver.get(category_url)
    time.sleep(2)

    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".x13eucookies__btn--accept-all"))
        )
        btn.click()
    except:
        pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    for _ in range(10):
        driver.execute_script("window.scrollBy(0,500)")
        time.sleep(1)

    product_urls = []
    cards = driver.find_elements(By.CSS_SELECTOR, "section#products article.product-miniature")
    print(f"🔍 Found {len(cards)} product cards on the page")

    for card in cards:
        try:
            if card.is_displayed():
                link = card.find_element(By.CSS_SELECTOR, "a.thumbnail").get_attribute("href")
                if link and "/gb/" in link:
                    print(f"🧲 Candidate product link: {link}")
                    product_urls.append(link)
        except:
            continue

    added_count = 0
    for url in product_urls:
        if added_count >= PRODUCTS_PER_CATEGORY:
            break

        driver.get(url)
        random_sleep(3, 6)
        data = fetch_product_data(driver)

        if not data:
            print("⚠️ Skipped a product due to scraping failure or missing data, retrying once...")
            time.sleep(2)
            driver.get(url)
            random_sleep(2, 4)
            data = fetch_product_data(driver)

        if data:
            hierarchical_category = CATEGORY_STRUCTURE.get(category_name, category_name)
            data["Categories"] = hierarchical_category
            results.append(data)
            added_count += 1
            print(f"✅ Product added: {data['Title']}")
        else:
            print("❌ Product skipped after retry")

driver.quit()

results = [r for r in results if r.get("Title")]

if results:
    with open("products_guiltfree.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print("Scraping complete — products_guiltfree.csv ready")
else:
    print("No data scraped")
