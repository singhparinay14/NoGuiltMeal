import os
import pandas as pd
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

# Load .env and initialize client
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INPUT_CSV = "products.csv"
OUTPUT_CSV = "products_enhanced.csv"

def enhance_with_gpt(system_prompt: str, user_prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT error: {e}")
        return ""

# Load data
df = pd.read_csv(INPUT_CSV)
df["Enhanced Short Description"] = ""
df["Enhanced Long Description"] = ""

SYSTEM_PROMPT = "You are a helpful assistant for rewriting e-commerce product descriptions in Polish."

for idx, row in tqdm(df.iterrows(), total=len(df)):
    name = row.get("Title", "").strip()
    nutrition_facts = row.get("Nutritional Facts", "").strip()
    short_desc = row.get("Short Description", "").strip()
    long_desc = row.get("Long Description", "").strip()

    if short_desc:
        user_prompt = (
            f"Write a short product description in Polish for the product: {name}.\n"
            f"Use the following original short description for context:\n"
            f"\"{short_desc}\"\n"
            "Follow Google Merchant Center guidelines (neutral tone, no promotional exaggerations, "
            "no excessive formatting, length approx. 500–750 characters). "
            "Begin with the focus keyword and incorporate 3–4 secondary SEO keywords that meet the following criteria:\n"
            "• Search Volume > 100\n• Paid Difficulty < 0.60\n• SEO Difficulty < 0.60\n"
            "Present 3–4 key highlights as bullet points starting with ✅. Ensure language is clear, "
            "compliant, and optimized for eCommerce product listings."
        )
        df.at[idx, "Enhanced Short Description"] = enhance_with_gpt(SYSTEM_PROMPT, user_prompt)

    if long_desc:
        user_prompt = (
            f"Write a 750-word long product description in Polish for the product: {name}.\n"
            f"Use the following original long description as input/context:\n"
            f"\"{long_desc}\"\n"
            "Start the content with the main focus keyword. Incorporate LSI keywords, long-tail keywords, "
            "and short-tail keywords that meet the following SEO criteria:\n"
            "• Search Volume > 100\n• Paid Difficulty < 0.60\n• SEO Difficulty < 0.60\n"
            "Ensure the tone is informative, neutral, and compliant with Google Merchant Center guidelines "
            "(no clickbait, no exaggerated claims).\n"
            "At the end of the description, include a clear and accurate tabela wartości odżywczych (nutrition table) "
            "formatted in basic HTML with the following nutrition facts about this product: \n"
            f"\"{nutrition_facts}\"\n"
            "Output the entire result in simple HTML suitable for a WordPress product page."
        )
        df.at[idx, "Enhanced Long Description"] = enhance_with_gpt(SYSTEM_PROMPT, user_prompt)

# Save
df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"✅ Enhanced descriptions written to {OUTPUT_CSV}")
