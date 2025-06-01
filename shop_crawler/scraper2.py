import csv
import re
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==================== CONFIGURATION ====================

CATEGORIES = [
    "Odżywki białkowe",
    "Kreatyna",
    "Tribulus Terrestris",
    "HMB",
    "BCAA",
    "Glutamina"
]
MAX_PRODUCTS_PER_CATEGORY = 5

# ==================== HELPER FUNCTIONS ====================

def random_sleep(min_s=1.5, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def extract_dieta_attribute(desc_text):
    desc_text = desc_text.lower()
    dieta_keywords = {
        "bez dodatku cukru": "Bez dodatku cukru",
        "bez cukru": "Bez cukru",
        "bez glutenu": "Bez glutenu",
        "bez laktozy": "Bez laktozy",
        "keto": "Keto",
        "niskowęglowodanowa": "Niskowęglowodanowa",
        "wegańska": "Wegańska",
        "wysokoproteinowa": "Wysokoproteinowa",
        "białkowa": "Wysokoproteinowa",
        "roślinna": "Wegańska"
    }
    found = {value for key, value in dieta_keywords.items() if key in desc_text}
    return ", ".join(sorted(found))

def extract_kalorii_attribute(nutrition_text):
    match = re.search(r'(\d+)\s*kcal', nutrition_text.lower())
    if not match:
        return ""
    try:
        kcal = float(match.group(1))
    except ValueError:
        return ""
    if kcal < 300:
        return "Poniżej 300 kalorii"
    elif kcal <= 500:
        return "301 -500 kalorii"
    elif kcal <= 1000:
        return "501 -1000 kalorii"
    else:
        return "Ponad 1000 kalorii"

def fetch_product_data(driver):
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1.product-name").text.strip()
    except:
        title = ""
    try:
        price = driver.find_element(By.CSS_SELECTOR, "span.price").text.strip()
    except:
        price = ""
    try:
        brand = driver.find_element(By.CSS_SELECTOR, ".manufacturer a").text.strip()
    except:
        brand = ""
    try:
        short_desc = driver.find_element(By.CSS_SELECTOR, "div.short-description").text.strip()
    except:
        short_desc = ""
    try:
        long_desc = driver.find_element(By.CSS_SELECTOR, "#product-description").text.strip()
    except:
        long_desc = ""
    try:
        image = driver.find_element(By.CSS_SELECTOR, "img.js-qv-product-cover").get_attribute("src").strip()
        image_urls = [image]
    except:
        image_urls = []

    try:
        nutrition_text = driver.find_element(By.CSS_SELECTOR, "#product-combinations").text.strip()
    except:
        nutrition_text = ""

    label_img = ""

    dieta_val = extract_dieta_attribute(short_desc + " " + long_desc)
    kalorii_val = extract_kalorii_attribute(nutrition_text)
    marki_val = brand

    return {
        "Title": title,
        "Price": price,
        "Brand": brand,
        "Short Description": short_desc,
        "Long Description": long_desc,
        "Nutrition Facts": nutrition_text,
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

# ==================== MAIN SCRIPT ====================

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get("https://strefasupli.pl/")

WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
random_sleep()

# ✅ Accept cookies popup
try:
    accept_btn = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Akceptuję')]"))
    )
    accept_btn.click()
    random_sleep(1, 2)
except:
    pass

results = []

for cat in CATEGORIES:
    print(f"\n🔍 Navigating to category: {cat}")

    try:
        driver.get("https://strefasupli.pl/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "_desktop_top_menu")))
        random_sleep()

        # ✅ Expand "Suplementy i odżywki" dropdown
        try:
            expand_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.navbar-toggler[data-target='#exCollapsingNavbar141']"))
            )
            driver.execute_script("arguments[0].click();", expand_btn)
            random_sleep(1, 2)
        except:
            print("⚠️ Could not expand 'Suplementy i odżywki' dropdown")

        # ✅ Expand any visible "" dropdowns if needed
        try:
            expand_icons = driver.find_elements(By.CSS_SELECTOR, "i.material-icons.add")
            for icon in expand_icons:
                try:
                    driver.execute_script("arguments[0].click();", icon)
                    random_sleep(0.5, 1.2)
                except:
                    continue
        except:
            pass

        # ✅ Click category link by visible text
        cat_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(), '{cat}')]"))
        )
        driver.execute_script("arguments[0].click();", cat_link)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/pl/p/']")))
        random_sleep()

        # ✅ Collect product links with auto pagination
        product_urls = []
        while len(product_urls) < MAX_PRODUCTS_PER_CATEGORY:
            cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/pl/p/']")
            for card in cards:
                href = card.get_attribute("href")
                if href and href not in product_urls:
                    product_urls.append(href)
            if len(product_urls) >= MAX_PRODUCTS_PER_CATEGORY:
                break
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "li.pagination-next a")
                if next_btn.is_displayed():
                    next_btn.click()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/pl/p/']")))
                    random_sleep()
                else:
                    break
            except:
                break

        print(f"🛒 Found {len(product_urls)} products for '{cat}'")

        for url in product_urls[:MAX_PRODUCTS_PER_CATEGORY]:
            try:
                driver.get(url)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
                random_sleep()
                data = fetch_product_data(driver)
                results.append(data)
            except Exception as e:
                print(f"❌ Failed to fetch product at {url} — {e}")

    except Exception as e:
        print(f"❌ Failed category '{cat}' — {e}")

driver.quit()

# ✅ Save to CSV
if results:
    with open("strefasupli_products.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print("\n✅ DONE: strefasupli_products.csv saved.")
else:
    print("⚠️ No data scraped.")
