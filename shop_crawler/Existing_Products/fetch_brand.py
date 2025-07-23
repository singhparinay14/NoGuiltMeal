import pandas as pd
from serpapi import GoogleSearch
from time import sleep

# === CONFIG ===
API_KEY = "a3f0b27afbbcb50ec457c422546b927c6d2043f57cc0b07b0637f767dc45dfb5"
products = pd.read_csv("export_for_reference.csv")
mapped   = pd.read_csv("mapped_brands.csv", encoding="ISO-8859-1")
missing  = sorted(set(products["Attribute 1 value(s)"].dropna()) - set(mapped["Brand"].dropna()))

results = []
for brand in missing:
    params = {
        "engine": "google",
        "q": f"{brand} o nas",
        "hl": "pl",
        "api_key": API_KEY
    }
    search = GoogleSearch(params)
    data = search.get_dict()
    # grab the first organic result
    link = ""
    if "organic_results" in data and len(data["organic_results"])>0:
        link = data["organic_results"][0].get("link","")
    print(f"{brand:25s} → {link}")
    results.append({"Brand": brand, "About Page URL": link})
    sleep(1)  # throttle

# save to CSV
pd.DataFrame(results).to_csv("mapped_brands_missing.csv", index=False, encoding="utf-8-sig")
print("✅ Done – see mapped_brands_missing.csv")
