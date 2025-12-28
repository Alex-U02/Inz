import easyocr
import numpy as np
import cv2

reader = easyocr.Reader(['pl', 'en'], gpu=False)

def easyocr_extract(image_bytes: bytes) -> str:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    result = reader.readtext(img, detail=0)
    return "\n".join(result)
