import os
import json
import requests

# ---------------------------------------
# DB – OCR
# ---------------------------------------
from app.db.init_db import init_db
from app.db.crud_ocr import save_ocr_results, clear_ocr

# ---------------------------------------
# KONFIGURACJA
# ---------------------------------------

API_URL = "http://localhost:8000/ocr"
PNG_DIR = "out/png"
RESULTS_FILE = "out/results/all_results.json"

ENGINES = ["easyocr", "pytesseract", "azure"]


# ============================================
# BATCH TEST
# ============================================

def run_batch():
    # Inicjalizacja bazy + czyszczenie OCR
    init_db()
    clear_ocr()

    print("DEBUG: working dir =", os.getcwd())
    print("DEBUG: PNG_DIR =", PNG_DIR)
    print("DEBUG: PNG_DIR exists:", os.path.exists(PNG_DIR))
    print("DEBUG: PNG_DIR contents:", os.listdir(PNG_DIR))

    all_results = {}

    for engine in ENGINES:
        print(f"\n=== ENGINE: {engine} ===")
        all_results[engine] = {}

        for filename in sorted(os.listdir(PNG_DIR)):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            img_path = os.path.join(PNG_DIR, filename)
            layout = os.path.splitext(filename)[0]

            with open(img_path, "rb") as f:
                response = requests.post(
                    API_URL,
                    files={"file": (filename, f, "image/png")},
                    data={"engine": engine, "layout": layout}
                )

            try:
                result = response.json()
            except Exception:
                result = {"error": "Invalid JSON response", "raw": response.text}

            all_results[engine][filename] = result
            print(f"      Processed: {filename}")

    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\nWszystkie wyniki zapisane do: {RESULTS_FILE}")


run_batch()
