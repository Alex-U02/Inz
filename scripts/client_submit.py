import requests
import argparse
import os
import json

API_URL = "http://localhost:8000/ocr"

def send_invoice(image_path: str, engine: str):
    if not os.path.exists(image_path):
        print(f"Plik nie istnieje: {image_path}")
        return

    with open(image_path, "rb") as f:
        response = requests.post(
            API_URL,
            files={"file": (os.path.basename(image_path), f, "image/png")},
            data={"engine": engine, "test_mode": True}
        )

    try:
        result = response.json()
    except Exception:
        print("Błąd: API zwróciło niepoprawny JSON")
        print("Odpowiedź:", response.text)
        return

    print("\n=== WYNIK OCR ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Wyślij pojedynczy obraz faktury do API OCR")
    parser.add_argument("image", help="Ścieżka do pliku PNG/JPG")
    parser.add_argument("--engine", default="easyocr",
                        choices=["easyocr", "pytesseract", "azure"],
                        help="Silnik OCR do użycia")

    args = parser.parse_args()
    send_invoice(args.image, args.engine)


main()
