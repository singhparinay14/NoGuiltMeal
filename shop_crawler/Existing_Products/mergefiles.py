import pandas as pd

# 1) Load the two files
mapped       = pd.read_csv("mapped_brands.csv",      encoding="ISO-8859-1")
missing_map  = pd.read_csv("mapped_brands_missing.csv", encoding="utf-8-sig")

# 2) Concatenate and drop any duplicate Brand entries, keeping the first occurrence
merged = pd.concat([mapped, missing_map], ignore_index=True)
merged = merged.drop_duplicates(subset="Brand", keep="first")

# 3) (Optional) sort by Brand name
merged = merged.sort_values("Brand").reset_index(drop=True)

# 4) Write back to disk (you can overwrite mapped_brands.csv or write a new file)
merged.to_csv("mapped_brands_merged.csv", index=False, encoding="utf-8-sig")

print("✅ Merged file written to mapped_brands_merged.csv")
