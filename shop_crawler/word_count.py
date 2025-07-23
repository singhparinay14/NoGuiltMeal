import os
from bs4 import BeautifulSoup

# === CONFIGURATION ===
ARTICLES_DIR = "generated_articles"  # Update if your folder name is different

def get_visible_word_count(html_text):
    """Extract visible text and count the number of words."""
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text(separator=' ')
    return len(text.split())

def main():
    print(f"📂 Checking articles in: {ARTICLES_DIR}\n")
    
    for filename in os.listdir(ARTICLES_DIR):
        if filename.endswith(".html"):
            filepath = os.path.join(ARTICLES_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                html_content = f.read()
                word_count = get_visible_word_count(html_content)
                print(f"📄 {filename} — {word_count} words")

if __name__ == "__main__":
    main()
