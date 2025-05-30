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

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def extract_dieta_attribute(desc_text):
    desc_text = desc_text.lower()
    dieta_map = {
        "no added sugar": "Bez dodatku cukru",
        "sugar free": "Bez cukru",
        "sugar-free": "Bez cukru",
        "no sugar": "Bez cukru",
        "gluten free": "Bez glutenu",
        "gluten-free": "Bez glutenu",
        "lactose free": "Bez laktozy",
        "lactose-free": "Bez laktozy",
        "keto": "Keto",
        "low carb": "Niskowęglowodanowa",
        "low-carb": "Niskowęglowodanowa",
        "vegan": "Wegańska",
        "high protein": "Wysokoproteinowa",
        "high-protein": "Wysokoproteinowa",
        "plant-based": "Wegańska",
        "plant based": "Wegańska",
    }

    dieta_terms = set()
    for keyword, polish in dieta_map.items():
        if keyword in desc_text:
            dieta_terms.add(polish)

    return ", ".join(sorted(dieta_terms))

def extract_kalorii_attribute(nutrition_text):
    # Match pattern: Calories: 164.85 (portion), 471.00 (100g)
    match = re.search(r'Calories:\s*[\d.,]+\s*\(portion\),\s*([\d.,]+)\s*\(100g\)', nutrition_text)
    if match:
        cal_str = match.group(1).replace(',', '.').strip()  # Normalize comma decimals
        try:
            calories = float(cal_str)
            if calories < 300:
                return "Poniżej 300 kalorii"
            elif 300 <= calories <= 500:
                return "301 -500 kalorii"
            elif 501 <= calories <= 1000:
                return "501 -1000 kalorii"
            else:
                return "Ponad 1000 kalorii"
        except ValueError:
            return ""
    return ""

def fetch_product_data(driver):
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1[itemprop='name']").text
    except:
        title = ""

    image_urls = []
    try:
        container = driver.find_element(By.CSS_SELECTOR, ".images-container")
        image_elements = container.find_elements(By.CSS_SELECTOR, "img.thumb.js-thumb")
        for img in image_elements:
            src = img.get_attribute("data-image-large-src") or img.get_attribute("src")
            if src and src.strip() not in image_urls:
                image_urls.append(src.strip())
    except:
        print("⚠️ Could not extract product images.")

    try:
        price = driver.find_element(By.CSS_SELECTOR, "span[itemprop='price']").text
    except:
        price = ""

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
        nutrition_tab = driver.find_element(By.XPATH, "//li[contains(., 'Nutritional values')]")
        nutrition_tab.click()
        time.sleep(1.5)
    except:
        print("⚠️ Nutritional tab not found.")

    nutrition_facts = []
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "nutri_main_div"))
        )

        rows = driver.find_elements(By.CSS_SELECTOR, ".nutri_main_div .row")
        for row in rows:
            try:
                label = row.find_element(By.CSS_SELECTOR, ".col-8_jp").text.strip()
                values = row.find_elements(By.CSS_SELECTOR, ".col-2_jp")
                per_portion = values[0].text.strip() if len(values) > 0 else ""
                per_100g = values[1].text.strip() if len(values) > 1 else ""
                nutrition_facts.append(f"{label}: {per_portion} (portion), {per_100g} (100g)")
            except:
                continue
    except Exception as e:
        print(f"⚠️ Failed to extract nutritional facts div: {e}")

    nutrition_flat = "; ".join(nutrition_facts)

    try:
        label_img = driver.find_element(By.CSS_SELECTOR, ".product-attachments img").get_attribute("src")
    except:
        label_img = ""

    # 🧠 Infer Attributes
    dieta_attr = extract_dieta_attribute(long_desc)
    kalorii_attr = extract_kalorii_attribute(nutrition_flat)

    return {
        "Title": title,
        "Price": price,
        "Brand": brand,
        "Short Description": short_desc,
        "Long Description": long_desc,
        "Nutrition Facts": nutrition_flat,
        "Nutrition Label URL": label_img,
        "images": ",".join(image_urls),
        "Dieta": dieta_attr,
        "Kalorii": kalorii_attr,
        "Marki": brand  # reusing brand for Woo attribute
    }

# 🚀 STARTING SCRIPT
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

driver.get("https://guiltfree.pl/gb/354-high-protein-products")
time.sleep(2)

try:
    cookie_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".x13eucookies__btn--accept-all"))
    )
    cookie_btn.click()
    print("✅ Accepted cookies.")
except:
    print("⚠️ Cookie banner not found or already dismissed.")

WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

print("🔄 Scrolling to load products...")
MAX_SCROLLS = 10
for _ in range(MAX_SCROLLS):
    driver.execute_script("window.scrollBy(0, 500);")
    time.sleep(1.5)

# ✅ Collect product URLs
product_urls = []
cards = driver.find_elements(By.CSS_SELECTOR, "section#products article.product-miniature")
for card in cards[:5]:  # limit for testing
    try:
        if card.is_displayed():
            link = card.find_element(By.CSS_SELECTOR, "a.thumbnail").get_attribute("href")
            product_urls.append(link)
            print(f"✅ Collected link: {link}")
    except:
        continue

# ✅ Scrape data
results = []
for url in product_urls:
    print(f"Scraping: {url}")
    driver.get(url)
    random_sleep()
    data = fetch_product_data(driver)
    if any(data.values()):
        results.append(data)

driver.quit()

# ✅ Save to CSV
if results:
    with open("products.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print("✅ Scraping complete! Check products.csv")
else:
    print("⚠️ No product data was extracted.")
