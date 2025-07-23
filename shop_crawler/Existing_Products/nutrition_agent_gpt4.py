# nutrition_agent_gpt4.py (Batch Processing: GPT-4o + Web Search Tool)

import os
import openai
import pandas as pd
import json
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

HTML_TEMPLATE = """
<div style='overflow-x:auto;'>
<h2>Tabela wartości odżywczych</h2>
<div style="overflow-x:auto;"><table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
<thead>
<tr style='background-color: #f2f2f2; text-align: left;'>
<th style='padding: 12px; border: 1px solid #ddd;'>Składnik</th>
<th style='padding: 12px; border: 1px solid #ddd;'>Wartość</th>
</tr>
</thead>
<tbody>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Wartość odżywcza</td><td style='padding: 12px; border: 1px solid #ddd;'>100 g</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Wartość energetyczna</td><td style='padding: 12px; border: 1px solid #ddd;'>{energy}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Tłuszcz</td><td style='padding: 12px; border: 1px solid #ddd;'>{fat}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>w tym kwasy tłuszczowe nasycone</td><td style='padding: 12px; border: 1px solid #ddd;'>{saturated_fat}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Węglowodany</td><td style='padding: 12px; border: 1px solid #ddd;'>{carbs}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>w tym cukry</td><td style='padding: 12px; border: 1px solid #ddd;'>{sugars}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Białko</td><td style='padding: 12px; border: 1px solid #ddd;'>{protein}</td></tr>
<tr><td style='padding: 12px; border: 1px solid #ddd;'>Sól</td><td style='padding: 12px; border: 1px solid #ddd;'>{salt}</td></tr>
</tbody>
</table></div>
</div>
"""

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for real-time information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to look up"
                }
            },
            "required": ["query"]
        }
    }
}

def get_nutrition_html(product_name):
    messages = [
        {
            "role": "system",
            "content": (
                "You're a nutrition assistant. Search the web for nutritional values per 100g or 100ml. "
                "Return ONLY JSON with fields: energy, fat, saturated_fat, carbs, sugars, protein, salt. "
                "Also provide a source URL in a separate line like: \nSOURCE: https://example.com"
            )
        },
        {
            "role": "user",
            "content": f"Wyszukaj wartości odżywcze dla produktu: {product_name}"
        }
    ]

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=[SEARCH_TOOL],
        tool_choice="auto",
        stream=False
    )

    if hasattr(response.choices[0].message, "tool_calls"):
        tool_call = response.choices[0].message.tool_calls[0]
        tool_messages = messages + [
            {"role": "assistant", "tool_calls": [tool_call]},
            {"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name,
             "content": f"query={product_name} wartości odżywcze"}
        ]

        final_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=tool_messages,
            stream=False
        )
        reply = final_response.choices[0].message.content
    else:
        reply = response.choices[0].message.content

    print("🧪 GPT reply:", reply)

    try:
        # Extract source line if present
        source_line = ""
        if "SOURCE:" in reply:
            source_line = reply.split("SOURCE:")[-1].strip()
            reply = reply.split("SOURCE:")[0].strip()

        clean_reply = reply.strip("`").replace("json", "").strip()
        json_data = json.loads(clean_reply)
        return HTML_TEMPLATE.format(**json_data), source_line
    except Exception as e:
        print("❌ Parse error:", e)
        return None, None

if __name__ == "__main__":
    input_csv = "products_missing_nutrition.csv"
    df = pd.read_csv(input_csv)
    output_rows = []

    for i, row in df.iterrows():
        name = row.get("Name")
        pid = row.get("ID")

        print(f"\n[{i+1}/{len(df)}] Processing: {name}")
        html, source = get_nutrition_html(name)

        if html:
            output_rows.append({
                "ID": pid,
                "Name": name,
                "NutritionHTML": html,
                "Source": source or "N/A"
            })

    pd.DataFrame(output_rows).to_csv("products_with_nutrition_filled.csv", index=False)
    print("\n✅ Finished processing all products.")
