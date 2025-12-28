from fastapi import FastAPI, UploadFile, File, Form
import time

from app.ocr.easyocr_adapter import easyocr_extract
from app.ocr.pytesseract_adapter import pytesseract_extract
from app.ocr.azure_adapter import azure_extract
from app.parsers.invoice_parser import parse_invoice

app = FastAPI(title="Invoice OCR API")

ENGINE_MAP = {
    "easyocr": easyocr_extract,
    "pytesseract": pytesseract_extract,
    "azure": azure_extract
}

@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    engine: str = Form(...)
):
    assert engine in ENGINE_MAP, "Unsupported engine"

    content = await file.read()
    start = time.time()
    raw_text = ENGINE_MAP[engine](content)
    duration_ms = int((time.time() - start) * 1000)

    parsed = parse_invoice(raw_text)

    return {
        "engine": engine,
        "duration_ms": duration_ms,
        "parsed": parsed,
        "raw_text": raw_text
    }