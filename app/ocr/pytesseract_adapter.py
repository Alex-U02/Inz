import io
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def pytesseract_extract_words(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes))

    data = pytesseract.image_to_data(
        img,
        lang="pol",
        output_type=pytesseract.Output.DICT
    )

    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue

        words.append({
            "text": text,
            "x": float(data["left"][i]),
            "y": float(data["top"][i]),
            "w": float(data["width"][i]),
            "h": float(data["height"][i]),
            "confidence": float(data["conf"][i]) / 100.0 
        })

    return words


def pytesseract_extract_text(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang="pol")
