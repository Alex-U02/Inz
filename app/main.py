from fastapi import FastAPI, UploadFile, File, Form
import time

from app.ocr.easyocr_adapter import easyocr_extract_words, easyocr_extract_text
from app.ocr.pytesseract_adapter import pytesseract_extract_words, pytesseract_extract_text
from app.ocr.azure_adapter import azure_extract_words, azure_extract_text

from app.parsers.invoice_parser import parse_invoice

app = FastAPI(title="Invoice OCR API")

ENGINE_MAP_WORDS = {
    "easyocr": easyocr_extract_words,
    "pytesseract": pytesseract_extract_words,
    "azure": azure_extract_words
}

ENGINE_MAP_TEXT = {
    "easyocr": easyocr_extract_text,
    "pytesseract": pytesseract_extract_text,
    "azure": azure_extract_text
}


@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    engine: str = Form(...),
    debug: bool = Form(False)
):
    assert engine in ENGINE_MAP_WORDS, "Unsupported engine"

    content = await file.read()

    start = time.time()
    words = ENGINE_MAP_WORDS[engine](content)
    raw_text = ENGINE_MAP_TEXT[engine](content)
    duration_ms = int((time.time() - start) * 1000)

    parsed = parse_invoice(raw_text, words, debug=debug)

    words_sorted = sorted(words, key=lambda w: (w["y"], w["x"]))

    response = {
        "engine": engine,
        "duration_ms": duration_ms,
        "parsed": parsed,
        "raw_text": raw_text,
        "words": words_sorted if debug else None
    }

    return response
