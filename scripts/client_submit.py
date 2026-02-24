import argparse
import json
import os
import sys
from typing import Optional

import requests

API_URL_DEFAULT = "http://127.0.0.1:8000/ocr"


def guess_mime(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext in [".tif", ".tiff"]:
        return "image/tiff"
    if ext == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def find_layout_file(folder: str, layout: str) -> str:
    exts = [".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff"]
    for ext in exts:
        p = os.path.join(folder, layout + ext)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"Nie znaleziono pliku dla layout='{layout}' w folderze '{folder}'. "
        f"Sprawdzane rozszerzenia: {', '.join(exts)}"
    )


def send_one(
    api_url: str,
    file_path: str,
    engine: str,
    layout: str,
    input_type: str,
    timeout: int,
    verbose: bool,
) -> requests.Response:
    mime = guess_mime(file_path)

    if verbose:
        size_mb = os.path.getsize(file_path) / 1024 / 1024
        print("=== REQUEST ===")
        print(f"url={api_url}")
        print(f"engine={engine} input_type={input_type} layout={layout}")
        print(f"file={file_path} mime={mime} size={size_mb:.2f}MB")
        print()

    with open(file_path, "rb") as f:
        return requests.post(
            api_url,
            files={"file": (os.path.basename(file_path), f, mime)},
            data={
                "engine": engine,
                "layout": layout,
                "input_type": input_type,
                "test_mode": True,  
            },
            timeout=timeout,
        )


def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Uruchom pojedynczy test OCR dla wybranego engine i layoutu z folderu i zapisz wynik do pliku JSON."
    )
    parser.add_argument("--folder", required=True, help="Folder z obrazami, np. out/jpg_photo")
    parser.add_argument("--layout", required=True, help="Nazwa layoutu (bez rozszerzenia), np. layout1_7")
    parser.add_argument(
        "--engine",
        default="easyocr",
        choices=["easyocr", "pytesseract", "azure"],
        help="Silnik OCR do użycia",
    )
    parser.add_argument(
        "--input-type",
        default="photo",
        choices=["clean", "photo", "scan"],
        help="Typ wejścia (dla spójności z API/benchmarkiem)",
    )
    parser.add_argument("--url", default=API_URL_DEFAULT, help="URL API OCR")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout (sekundy)")
    parser.add_argument("--verbose", action="store_true", help="Wypisz szczegóły requestu")
    parser.add_argument(
        "--out",
        default=None,
        help="Ścieżka pliku wynikowego JSON. Domyślnie: out/debug/<layout>_<engine>.json",
    )

    args = parser.parse_args()

    try:
        file_path = find_layout_file(args.folder, args.layout)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2)

    out_path = args.out or os.path.join("out", "debug", f"{args.layout}_{args.engine}.json")
    ensure_dir(out_path)

    resp = send_one(
        api_url=args.url,
        file_path=file_path,
        engine=args.engine,
        layout=args.layout,
        input_type=args.input_type,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    print(f"HTTP: {resp.status_code}")
    print(f"Response Content-Type: {resp.headers.get('content-type', '')}")

    payload = {
        "request": {
            "engine": args.engine,
            "layout": args.layout,
            "input_type": args.input_type,
            "folder": args.folder,
            "file_path": file_path,
            "url": args.url,
        },
        "response": {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
        },
    }

    try:
        payload["response"]["json"] = resp.json()
    except Exception:
        payload["response"]["json"] = None

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved result to: {out_path}")

    if payload["response"]["json"] is not None:
        status = payload["response"]["json"].get("status")
        err = payload["response"]["json"].get("error")
        if status:
            print(f"API status: {status}")
        if err:
            print(f"API error: {err}")


if __name__ == "__main__":
    main()