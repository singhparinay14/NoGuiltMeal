import pandas as pd

# === Load both CSV files ===
reference_csv = "export_for_reference_enhanced.csv"
nutrition_csv = "products_with_nutrition_filled.csv"

df_reference = pd.read_csv(reference_csv, encoding="utf-8")
df_nutrition = pd.read_csv(nutrition_csv, encoding="utf-8")

# === Merge on 'ID' column ===
df_merged = df_reference.merge(
    df_nutrition[["ID", "NutritionHTML", "Source"]],
    on="ID",
    how="left"
)

# === Save to new file ===
df_merged.to_csv("export_enhanced_with_nutrition.csv", index=False, encoding="utf-8")

print("✅ Merged successfully: export_enhanced_with_nutrition.csv created.")
