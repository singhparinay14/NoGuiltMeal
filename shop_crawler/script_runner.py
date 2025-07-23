import subprocess
import time
import sys
import os

# Use venv's Python explicitly
venv_python = os.path.join("venv", "Scripts", "python.exe")

# Number of products to scrape per category (modify here)
num_products = 15
enable_headless = True  # Toggle this to False if you want the browser visible


# Each tuple = (script file, friendly name)
scripts = [
    #("scraper_guiltfree.py", "GuiltFree.pl"),
    ("scraper_sportmax.py", "Sport-Max.pl"),
    #("scraper_strefamocy.py", "StrefaMocy.pl"),
    #("scraper_swiatsupli.py", "SwiatSupli.pl"),
]

for script, name in scripts:
    print(f"\n🚀 Starting: {name} ({script}) with {num_products} products/category")

    # Prepare the base command
    cmd = [venv_python, script, "--count", str(num_products)]
    if enable_headless:
        cmd.append("--headless")
        
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✅ Finished: {name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {name}")
        print(e)

    time.sleep(10)

print("\n🎉 All scraping scripts executed.")
