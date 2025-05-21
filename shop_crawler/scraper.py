from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import random

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def fetch_product_data(driver):
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1[itemprop='name']").text
    except:
        title = ""

    try:
        price = driver.find_element(By.ID, "our_price_display").text
    except:
        price = ""

    try:
        brand = driver.find_element(By.CSS_SELECTOR, ".product-manufacturer img").get_attribute("alt")
    except:
        brand = ""

    # ✅ Short description (highlighted yellow box)
    try:
        short_desc = driver.find_element(By.CSS_SELECTOR, "div[itemprop='description']").get_attribute("innerText").strip()
    except:
        short_desc = ""

    # ✅ Long description (detailed spec lower down)
    try:
        long_desc = driver.find_element(By.ID, "description").get_attribute("innerText").strip()
    except:
        long_desc = ""

    # ✅ Click the Nutritional Values tab
    try:
        nutrition_tab = driver.find_element(By.XPATH, "//li[contains(., 'Nutritional values')]")
        nutrition_tab.click()
        time.sleep(1.5)
    except:
        print("⚠️ Nutritional tab not found.")

    # ✅ Extract from .nutri_main_div layout
    nutrition_facts = []
    try:
        # Wait for content inside .nutri_main_div to load
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


    # ✅ Nutrition label image
    try:
        label_img = driver.find_element(By.CSS_SELECTOR, ".product-attachments img").get_attribute("src")
    except:
        label_img = ""

    return {
        "Title": title,
        "Price": price,
        "Brand": brand,
        "Short Description": short_desc,
        "Long Description": long_desc,
        "Nutrition Facts": nutrition_flat,
        "Nutrition Label URL": label_img
    }

# ========================
# 🚀 STARTING SCRIPT
# ========================
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # for debugging, keep browser visible

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ✅ Open category page
driver.get("https://guiltfree.pl/gb/354-high-protein-products")
time.sleep(2)

# ✅ Accept cookies early
try:
    cookie_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".x13eucookies__btn--accept-all"))
    )
    cookie_btn.click()
    print("✅ Accepted cookies.")
except:
    print("⚠️ Cookie banner not found or already dismissed.")

WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

# ✅ Scroll to force product loading
print("🔄 Scrolling to load products...")
MAX_SCROLLS = 10
scroll_count = 0

while scroll_count < MAX_SCROLLS:
    driver.execute_script("window.scrollBy(0, 500);")
    time.sleep(1.5)
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, "article.product-miniature")
        visible_cards = [c for c in cards if c.is_displayed()]
        if len(visible_cards) > 0:
            print(f"✅ Found {len(visible_cards)} product cards.")
            break
    except:
        pass
    scroll_count += 1

if scroll_count == MAX_SCROLLS:
    print("❌ Could not find visible product cards after scrolling.")
    driver.quit()
    exit()



# ✅ Get visible product cards and extract links
product_urls = []
cards = driver.find_elements(By.CSS_SELECTOR, "section#products article.product-miniature")
for card in cards[:20]:  # limit for testing
    try:
        if card.is_displayed():
            link = card.find_element(By.CSS_SELECTOR, "a.thumbnail").get_attribute("href")
            product_urls.append(link)
            print(f"✅ Collected link ({i+1}): {link}")
    except:
        continue

print(f"Found {len(product_urls)} product URLs.")
for url in product_urls:
    print(f"→ {url}")

# ✅ Visit product pages and extract data
results = []
for url in product_urls:
    print(f"Scraping: {url}")
    driver.get(url)
    random_sleep()
    data = fetch_product_data(driver)
    if any(data.values()):  # skip fully empty results
        results.append(data)

driver.quit()

# ✅ Save to CSV
if results:
    with open("products.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print("✅ Scraping complete! Check products.csv")
else:
    print("⚠️ No product data was extracted.")
