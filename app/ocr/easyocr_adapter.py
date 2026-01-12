import easyocr
import numpy as np
import cv2

reader = easyocr.Reader(['pl', 'en'], gpu=False)

def easyocr_extract_words(image_bytes: bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    result = reader.readtext(img, detail=1, paragraph=False)

    words = []
    for bbox, text, conf in result:
        x = bbox[0][0]
        y = bbox[0][1]
        w = bbox[1][0] - bbox[0][0]
        h = bbox[2][1] - bbox[1][1]

        words.append({
            "text": text,
            "x": float(x),
            "y": float(y),
            "w": float(w),
            "h": float(h),
            "confidence": float(conf)
        })

    return words


def easyocr_extract_text(image_bytes: bytes) -> str:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    result = reader.readtext(img, detail=0)
    return "\n".join(result)
