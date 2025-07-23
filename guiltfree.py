from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
import random
from time import sleep
import csv

# Function to fetch product data
def fetch_product_data(driver):
    # Fetch data from the details page
    product_title = driver.find_element(By.XPATH, '//*[@id="txt-col-prod"]/div/div/h1').text
    price = driver.find_element(By.XPATH, '//*[@id="add-to-cart-or-refresh"]/div[3]/div[1]/div').text
    brand = driver.find_element(By.XPATH, '//*[@id="txt-col-prod"]/div/div/div[2]/span/a').text
    short_description = driver.find_element(By.XPATH, '//*[@id="product-description-short-3439"]/p').text
    long_description = driver.find_element(By.XPATH, '//*[@id="description"]').text

    return {
        "Product Title": product_title,
        "Price": price,
        "Brand": brand,
        "Short Description": short_description,
        "Long Description": long_description
    }

# Function for random sleep
def random_sleep(min_sleep=1, max_sleep=10):
    duration = random.uniform(min_sleep, max_sleep)
    print(f"Sleeping for {duration:.2f} seconds...")
    sleep(duration)

# Function to save data to CSV file
def save_to_csv(data, filename):
    with open(filename, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

# Query input
domain = input('Enter your target domain: ')
search_query = input('Enter your search query: ')

# Set up Chrome webdriver options
options = webdriver.ChromeOptions()
options.add_experimental_option('detach', True)

# Open Chrome in webdriver
driver = webdriver.Chrome(options=options)

# Construct the URL
url = "https://www.{}".format(domain)

# Navigate to the URL
driver.get(url)
print(url)

# Accept cookies (if applicable)
try:
    cookies_accept = driver.find_element(By.XPATH, '//*[@id="x13eucookies-box"]/div[3]/div/div[3]/button')
    cookies_accept.click()
except:
    pass

# Find the search box element and submit the form
try:
    search_box = driver.find_element(By.XPATH, '//*[@id="dgwt-wcas-search-input-1"]')
    search_box.send_keys(search_query)
    random_sleep()
    search_box.submit()
except Exception as e:
    print(f"Error while submitting the search query: {e}")

# Random sleep after submitting the search query
random_sleep()

# Get the page source using Selenium
page_source = driver.page_source
soup = BeautifulSoup(page_source, 'html.parser')

# Find product cards using BeautifulSoup and the correct XPath
product_cards = soup.select('//*[@id="main"]/div/section/ul/li[1]')

print(product_cards)