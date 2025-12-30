import os
import json
import requests

API_URL = "http://localhost:8000/ocr"
PNG_DIR = "out/png"
RESULTS_FILE = "out/results/all_results.json"

# Używamy skrótów zgodnych z ENGINE_MAP w API
ENGINES = ["easyocr", "pytesseract"]


def run_batch():
    print("DEBUG: working dir =", os.getcwd())
    print("DEBUG: PNG_DIR =", PNG_DIR)
    print("DEBUG: PNG_DIR exists:", os.path.exists(PNG_DIR))
    print("DEBUG: PNG_DIR contents:", os.listdir(PNG_DIR))

    all_results = {}

    for engine in ENGINES:
        print(f"\n=== ENGINE: {engine} ===")
        all_results[engine] = {}

        # iterujemy po pojedynczych plikach PNG
        for filename in sorted(os.listdir(PNG_DIR)):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            img_path = os.path.join(PNG_DIR, filename)
            print(f"  → Processing: {filename}")

            # wysyłamy obraz do API
            with open(img_path, "rb") as f:
                response = requests.post(
                    API_URL,
                    files={"file": (filename, f, "image/png")},
                    data={"engine": engine}
                )

            try:
                result = response.json()
            except Exception:
                result = {"error": "Invalid JSON response", "raw": response.text}

            all_results[engine][filename] = result

            print(f"      Processed: {filename}")

    # zapisujemy wszystko do jednego pliku
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\nWszystkie wyniki zapisane do: {RESULTS_FILE}")

run_batch()
