import os
import re
import gspread
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIGURATION ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SPREADSHEET_ID = "1UWR5F3c20ZSc7kpf9eKz8OpC5bLFdoHGPwF7F0Apsm0"
GOOGLE_KEY_FILE = os.getenv("GOOGLE_KEY_PATH")
WORKSHEET_NAME = "Input"
OUTPUT_DIR = "generated_articles"
KEYWORDS_DIR = "generated_keywords"
PROCESSED_LOG = "processed_titles.txt"

# === SETUP ===
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(KEYWORDS_DIR, exist_ok=True)

def slugify_filename(title):
    filename = title.lower().replace(" ", "_")
    filename = re.sub(r'[^\w_]', '', filename)
    return filename.strip()

def load_titles_from_google_sheet(json_keyfile_path, spreadsheet_id, worksheet_name='Input'):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df['Title'].dropna().tolist()

# === PROMPTS ===
def keyword_prompt(title):
    return f"""You are an SEO expert in Poland and your task is to create a list of relevant keywords for a blog article "{title}". 
Filter the results where "Search Volume" > 100, "Paid Difficulty" < 0.50, and "SEO Difficulty" < 0.50. 
Group keywords into: (1) LSI, (2) Long-tail, (3) Short-tail. Output in Polish and use a clear table format."""

def outline_prompt(title):
    return f"""Generate a detailed outline for a Polish blog article titled "{title}". 
Split the article into at least 6 sections, each with a heading and a short description. 
Return in the following format:
1. [Section Title] - [Short Summary]
2. ...
Only write in Polish and do not include HTML."""

def section_prompt(section_title, section_summary, keywords):
    return f"""Write a detailed section in Polish for a blog article. Use valid HTML tags. 
The section title is: "{section_title}". Expand the following summary into at least 200 words:
"{section_summary}"

Include 2–3 of the following SEO keywords: {keywords}
Use <h2> for the section title, and include a <p> tag with keywords listed below it.
Only output valid HTML content."""

def ask_openai(prompt, temperature=0.7, max_tokens=1000):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def parse_outline(raw_outline):
    lines = raw_outline.strip().split("\n")
    parsed = []
    for line in lines:
        match = re.match(r'\d+\.\s*(.*?)\s*-\s*(.*)', line)
        if match:
            title, summary = match.groups()
            parsed.append((title.strip(), summary.strip()))
    return parsed

def generate_article_by_sections(title, keywords, min_words=1000, max_attempts=3):
    for attempt in range(max_attempts):
        print(f"🧱 Generating outline (attempt {attempt+1})...")
        raw_outline = ask_openai(outline_prompt(title), max_tokens=1000)
        outline = parse_outline(raw_outline)

        article_sections = []
        for idx, (sec_title, sec_summary) in enumerate(outline, 1):
            print(f"📝 Generating section {idx}: {sec_title}")
            section_html = ask_openai(section_prompt(sec_title, sec_summary, keywords), max_tokens=1200)
            article_sections.append(section_html)

        full_article = "\n\n".join(article_sections)
        word_count = len(full_article.split())

        if word_count >= min_words:
            print(f"✅ Full article OK: {word_count} words")
            return full_article
        else:
            print(f"⚠️ Article too short: {word_count} words — retrying...")

    raise ValueError(f"Generated article too short after {max_attempts} attempts.")

# === LOGGING ===
def is_processed(title):
    if not os.path.exists(PROCESSED_LOG):
        return False
    with open(PROCESSED_LOG, 'r', encoding='utf-8') as f:
        return title.strip() in f.read()

def mark_as_processed(title):
    with open(PROCESSED_LOG, 'a', encoding='utf-8') as f:
        f.write(title.strip() + "\n")

# === MAIN ===
def main():
    titles = load_titles_from_google_sheet(GOOGLE_KEY_FILE, SPREADSHEET_ID, WORKSHEET_NAME)

    for i, title in enumerate(titles):
        if is_processed(title):
            print(f"⏭️ Skipping already processed: {title}")
            continue

        print(f"\n[{i+1}/{len(titles)}] Processing: {title}")

        try:
            # Step 1: Generate keywords
            keyword_response = ask_openai(keyword_prompt(title))
            keyword_file = os.path.join(KEYWORDS_DIR, f"keywords_{i+1:02d}.txt")
            with open(keyword_file, "w", encoding="utf-8") as f:
                f.write(keyword_response)

            # Step 2: Generate section-based article
            article_html = generate_article_by_sections(title, keyword_response)

            # Step 3: Save article
            safe_title = slugify_filename(title)
            article_file = os.path.join(OUTPUT_DIR, f"{safe_title}.html")
            with open(article_file, "w", encoding="utf-8") as f:
                f.write(article_html)

            mark_as_processed(title)
            print(f"✅ Article saved: {article_file}")

        except Exception as e:
            print(f"❌ Error processing '{title}': {str(e)}")

    print("\n🎉 All titles processed!")

if __name__ == "__main__":
    main()
