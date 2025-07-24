import os
import json
import pandas as pd
import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner, WebSearchTool

# ─── Configuration ───────────────────────────────────────────────────────────────

load_dotenv()  # expects OPENAI_API_KEY in your environment

HTML_TEMPLATE = """
<div style='overflow-x:auto;'>
  <h2>Tabela wartości odżywczych</h2>
  <div style="overflow-x:auto;">
    <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-family: Arial, sans-serif;'>
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
    </table>
  </div>
</div>
"""

# ─── Build the Agent ─────────────────────────────────────────────────────────────

agent = Agent(
    name="NutritionAgent",
    instructions="""
You are a nutrition expert. For a given product name:
1. Use the WebSearchTool to search "<product> wartości odżywcze".
2. Extract per-100g nutrition values (convert if only per-serving found).
3. Return ONLY a JSON object with keys: energy, fat, saturated_fat, carbs, sugars, protein, salt.
4. On a new line, add: SOURCE: <URL you used>
5. If no data is found, return exactly: No data found
""",
    tools=[WebSearchTool()],
)

# ─── Main Loop ──────────────────────────────────────────────────────────────────

async def main():
    df = pd.read_csv("products_missing_nutrition.csv", encoding="utf-8")
    output = []

    for _, row in df.iterrows():
        pid, name = row["ID"], row["Name"]
        print(f"Processing: {name}")
        run_result = await Runner.run(agent, f"Podaj wartości odżywcze na 100g dla produktu: {name}")
        reply = run_result.final_output.strip()

        if reply == "No data found":
            html, source, flag = "", "", 0
        else:
            # Split off SOURCE line
            if "SOURCE:" in reply:
                json_part, source_part = reply.split("SOURCE:", 1)
                source = source_part.strip()
            else:
                json_part, source = reply, ""
            # Try parsing JSON
            try:
                nutrition = json.loads(json_part)
                html = HTML_TEMPLATE.format(**nutrition)
                flag = 1
            except json.JSONDecodeError:
                html, source, flag = "", "", 0

        output.append({
            "ID":             pid,
            "Name":           name,
            "NutritionHTML":  html,
            "Source":         source,
            "NutritionFound": flag
        })

    pd.DataFrame(output).to_csv(
        "products_with_nutrition_filled.csv",
        index=False,
        encoding="utf-8"
    )
    print("✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
