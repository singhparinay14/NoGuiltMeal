# Scraper for GuiltFree.pl across multiple categories with GTIN extraction and category tagging

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

# === CATEGORY CONFIGURATION ===
CATEGORY_URLS = [
    "https://guiltfree.pl/gb/354-high-protein-products",  # Protein Snacks
    "https://guiltfree.pl/gb/355-protein-supplements?manufacturers=biotech-usa,olimp,optimum-nutrition",  # Proteins
    "https://guiltfree.pl/gb/639-sport-suplements",  # Supplements
    "https://guiltfree.pl/gb/393-healthy-sweets?categories=chocolate-without-sugar,chocolates-and-bonbons-without-sugar,cookies-without-sugar,wafers-without-sugar-and-light",  # snacks
    "https://guiltfree.pl/gb/389-peanut-butters",  # Spreads
    "https://guiltfree.pl/gb/344-energy-drinks-without-sugar",  # Energy Drinks
    "https://guiltfree.pl/gb/349-plant-based-drinks",  # Shakes and Drinks
    "https://guiltfree.pl/gb/332-light-bread",  # Breads
    "https://guiltfree.pl/gb/366-salty-light-snacks?categories=protein-chips,veggie-crisps",  # Chips
    "https://guiltfree.pl/gb/380-ketchup-and-dressing?categories=dressings-zero-kcal,ketchup-without-sugar,light-mayonnaise,sauces-bbq-zero-kcal,zero-kcal-dips",  # Sauces and Dips
    "https://guiltfree.pl/gb/437-spices-without-salt",  # Herbs and Spices
]

# Mapping from URL to a human-readable category name
CATEGORY_NAMES = {
    "https://guiltfree.pl/gb/354-high-protein-products": "Protein Snacks",
    "https://guiltfree.pl/gb/355-protein-supplements?manufacturers=biotech-usa,olimp,optimum-nutrition": "Proteins",
    "https://guiltfree.pl/gb/639-sport-suplements": "Supplements",
    "https://guiltfree.pl/gb/393-healthy-sweets?categories=chocolate-without-sugar,chocolates-and-bonbons-without-sugar,cookies-without-sugar,wafers-without-sugar-and-light": "Snacks",
    "https://guiltfree.pl/gb/389-peanut-butters": "Spreads",
    "https://guiltfree.pl/gb/344-energy-drinks-without-sugar": "Energy Drinks",
    "https://guiltfree.pl/gb/349-plant-based-drinks": "Shakes and Drinks",
    "https://guiltfree.pl/gb/332-light-bread": "Breads",
    "https://guiltfree.pl/gb/366-salty-light-snacks?categories=protein-chips,veggie-crisps": "Chips",
    "https://guiltfree.pl/gb/380-ketchup-and-dressing?categories=dressings-zero-kcal,ketchup-without-sugar,light-mayonnaise,sauces-bbq-zero-kcal,zero-kcal-dips": "Sauces and Dips",
    "https://guiltfree.pl/gb/437-spices-without-salt": "Herbs and Spices",
}

# === HELPER FUNCTIONS ===

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def extract_dieta_attribute(desc_text):
    desc_text = desc_text.lower()
    dieta_map = {
        "no added sugar": "Bez dodatku cukru",
        "sugar free": "Bez cukru",
        "gluten free": "Bez glutenu",
        "lactose free": "Bez laktozy",
        "keto": "Keto",
        "low carb": "Niskowęglowodanowa",
        "vegan": "Wegańska",
        "high protein": "Wysokoproteinowa",
        "plant based": "Wegańska",
    }
    terms = {pl for en, pl in dieta_map.items() if en in desc_text}
    return ", ".join(sorted(terms))

def extract_kalorii_attribute(nutrition_text):
    match = re.search(r'Calories:\s*[\d\.,]+\s*\(portion\),\s*([\d\.,]+)\s*\(100g\)', nutrition_text)
    if not match:
        return ""
    cal_str = match.group(1).replace(",", ".")
    try:
        cal = float(cal_str)
    except ValueError:
        return ""
    if cal < 300:
        return "Poniżej 300 kalorii"
    if cal <= 500:
        return "301 -500 kalorii"
    if cal <= 1000:
        return "501 -1000 kalorii"
    return "Ponad 1000 kalorii"

def fetch_product_data(driver):

    # Skip product if title or page body is empty (broken or blank page)
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
        if not body_text or "Product not found" in body_text or "Page not available" in body_text:
            print("⚠️ Empty or broken product page — skipping")
            return None
    except:
        print("⚠️ Could not load product page — skipping")
        return None

    # — Title —
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1[itemprop='name']").text.strip()
    except:
        title = ""

    # — Images —
    image_urls = []
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, ".images-container img.thumb.js-thumb")
        for img in imgs:
            src = img.get_attribute("data-image-large-src") or img.get_attribute("src")
            if src and src not in image_urls:
                image_urls.append(src.strip())
    except:
        pass

    # — Price —
    try:
        price = driver.find_element(By.CSS_SELECTOR, "span[itemprop='price']").text.strip()
    except:
        price = ""

    # — Brand (Marki) —
    try:
        brand = driver.find_element(By.CSS_SELECTOR, ".product-manufacturer span a").text.strip()
    except:
        brand = ""

    # — Descriptions —
    try:
        short_desc = driver.find_element(By.CSS_SELECTOR, "div[itemprop='description']").get_attribute("innerText").strip()
    except:
        short_desc = ""
    try:
        long_desc = driver.find_element(By.ID, "description").get_attribute("innerText").strip()
    except:
        long_desc = ""

    # — Nutrition Facts —
    try:
        driver.find_element(By.XPATH, "//li[contains(., 'Nutritional values')]").click()
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

    # — Nutrition-label image —
    try:
        label_img = driver.find_element(By.CSS_SELECTOR, ".product-attachments img").get_attribute("src").strip()
    except:
        label_img = ""

    # — Derived Attributes —
    dieta_val = extract_dieta_attribute(short_desc + " " + long_desc)
    kalorii_val = extract_kalorii_attribute(nutrition_flat)
    marki_val = brand

    # — GTIN Extraction from JSON-LD —
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

    # — Build base dict —
    data = {
        "GTIN": gtin,
        "Title": title,
        "Price": price,
        "Brand": brand,
        "Short Description": short_desc,
        "Long Description": long_desc,
        "Nutrition Facts": nutrition_flat,
        "Nutrition Label URL": label_img,
        "images": ",".join(image_urls),
    }

    # — Append Woo Attributes in correct format —
    data.update({
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
    })

    return data

# === MAIN SCRIPT ===

options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Enable headless mode
options.add_argument("--disable-gpu")  # Optional: improves compatibility
options.add_argument("--window-size=1920,1080")  # Ensures full layout rendering
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

results = []

for category_url in CATEGORY_URLS:
    category_name = CATEGORY_NAMES.get(category_url, "")
    print(f"\n🔍 Scraping category: {category_name} ({category_url})")

    driver.get(category_url)
    time.sleep(2)

    # — Accept cookies if shown —
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".x13eucookies__btn--accept-all"))
        )
        btn.click()
    except:
        pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # — Scroll to load all products —
    for _ in range(10):
        driver.execute_script("window.scrollBy(0,500)")
        time.sleep(1)

    # — Collect product links —
    product_urls = []
    cards = driver.find_elements(By.CSS_SELECTOR, "section#products article.product-miniature")
    for card in cards[:2]:  # Limit per category; adjust as needed
        try:
            if card.is_displayed():
                link = card.find_element(By.CSS_SELECTOR, "a.thumbnail").get_attribute("href")
                product_urls.append(link)
        except:
            continue

    product_counter = 0

    # — Visit each product and extract data —
    for url in product_urls:
        driver.get(url)
        random_sleep(3, 6)  # Increased sleep range
        data = fetch_product_data(driver)
        product_counter += 1
        if data:
            data["Categories"] = category_name
            results.append(data)
        if product_counter % 20 == 0:
            print("⏳ Cooldown... sleeping for 15 seconds to prevent server overload.")
            time.sleep(15)

driver.quit()

# — Save CSV with BOM so Polish chars import cleanly —

if results:
    with open("products.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print("✅ Scraping complete — products.csv ready for WooCommerce import")
else:
    print("⚠️ No data scraped")
