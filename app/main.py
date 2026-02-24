from fastapi import FastAPI, UploadFile, File, Form
import time

# ---------------------------------------
# OCR Engines
# ---------------------------------------
from app.ocr.easyocr_adapter import easyocr_extract_words, easyocr_extract_text
from app.ocr.pytesseract_adapter import pytesseract_extract_words, pytesseract_extract_text
from app.ocr.azure_adapter import run_azure_ocr

# ---------------------------------------
# Parsers
# ---------------------------------------
from app.parsers.invoice_parser import parse_invoice

# ---------------------------------------
# DB – OCR
# ---------------------------------------
from app.db.init_db import init_db
from app.db.crud_ocr import save_ocr_results

# ---------------------------------------
# FastAPI
# ---------------------------------------
app = FastAPI(title="Invoice OCR API")

# Inicjalizacja bazy przy starcie API
init_db()

ENGINE_MAP_WORDS = {
    "easyocr": easyocr_extract_words,
    "pytesseract": pytesseract_extract_words,
}

ENGINE_MAP_TEXT = {
    "easyocr": easyocr_extract_text,
    "pytesseract": pytesseract_extract_text,
}


@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    engine: str = Form(...),
    layout: str = Form(None),
    input_type: str = Form("clean"),
    test_mode: bool = Form(False),  
):
    assert engine in ["easyocr", "pytesseract", "azure"], "Unsupported engine"
    assert input_type in ["clean", "photo", "scan"], "Unsupported input_type"

    content = await file.read()

    if engine == "azure":
        start = time.time()
        parsed = run_azure_ocr(content)   
        duration_ms = int((time.time() - start) * 1000)
        raw_text = None
        words = None
    else:
        start = time.time()
        words = ENGINE_MAP_WORDS[engine](content)
        raw_text = ENGINE_MAP_TEXT[engine](content)
        duration_ms = int((time.time() - start) * 1000)

        parsed = parse_invoice(raw_text, words, debug=False)

    if not test_mode:
        save_ocr_results(
            parsed=parsed,
            engine=engine,
            raw_text=raw_text,
            duration_ms=duration_ms,
            layout=layout,
            input_type=input_type
        )

    return {
        "engine":  engine,
        "duration_ms": duration_ms,
        "parsed": parsed,
        "raw_text": raw_text,
        "words": words 
    }