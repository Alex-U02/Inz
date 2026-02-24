import os
import json
import requests
import argparse

# ---------------------------------------
# DB – OCR
# ---------------------------------------
from app.db.init_db import init_db
from app.db.crud_ocr import clear_ocr

# ---------------------------------------
# KONFIGURACJA
# ---------------------------------------

API_URL = "http://localhost:8000/ocr"
RESULTS_FILE = "out/results/all_results.json"

ENGINES = ["easyocr", "pytesseract", "azure"]

def guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    return "application/octet-stream"


# ============================================
# ARGUMENTS
# ============================================

def parse_args():
    p = argparse.ArgumentParser(description="Batch test OCR dla clean/photo/scan w jednym uruchomieniu")
    p.add_argument("--root", default="out", help="Katalog bazowy (domyślnie: out)")
    p.add_argument("--clear", action="store_true", help="Wyczyść OCR w bazie przed startem")
    return p.parse_args()


# ============================================
# BATCH TEST
# ============================================

def run_batch(root: str, clear_first: bool):
    # Inicjalizacja bazy + (opcjonalnie) czyszczenie OCR
    init_db()
    if clear_first:
        clear_ocr()

    folders = [
        ("clean", os.path.join(root, "png_clean")),
        ("photo", os.path.join(root, "jpg_photo")),
        ("scan",  os.path.join(root, "png_scan")),
    ]

    print("DEBUG: working dir =", os.getcwd())
    print("DEBUG: root =", root)
    print("DEBUG: folders =", folders)

    # all_results[engine][input_type][filename] = result
    all_results = {engine: {"clean": {}, "photo": {}, "scan": {}} for engine in ENGINES}

    for engine in ENGINES:
        print(f"\n=== ENGINE: {engine} ===")

        for input_type, png_dir in folders:
            print(f"\n--- INPUT TYPE: {input_type} ---")
            print("DEBUG: PNG_DIR =", png_dir)
            print("DEBUG: PNG_DIR exists:", os.path.exists(png_dir))

            if not os.path.exists(png_dir):
                print("WARN: Brak folderu, pomijam:", png_dir)
                continue

            try:
                dir_files = sorted(os.listdir(png_dir))
            except Exception as e:
                print(f"WARN: Nie mogę odczytać katalogu {png_dir}: {e}")
                continue

            print("DEBUG: file count =", len(dir_files))

            for filename in dir_files:
                if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue

                img_path = os.path.join(png_dir, filename)
                layout = os.path.splitext(filename)[0]

                mime = guess_mime(filename)
                with open(img_path, "rb") as f:
                    response = requests.post(
                        API_URL,
                        files={"file": (filename, f, mime)},
                        data={"engine": engine, "layout": layout, "input_type": input_type},
                        timeout=180,
                    )

                try:
                    result = response.json()
                except Exception:
                    result = {
                        "error": "Invalid JSON response",
                        "status_code": response.status_code,
                        "raw": response.text,
                    }

                all_results[engine][input_type][filename] = result
                print(f"      Processed: {input_type}/{filename}")

    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\nWszystkie wyniki zapisane do: {RESULTS_FILE}")


if __name__ == "__main__":
    args = parse_args()
    run_batch(args.root, args.clear)