from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import GroundTruthInvoice, OCRInvoice

def compare_invoice(layout: str):
    db: Session = SessionLocal()

    gt = db.query(GroundTruthInvoice).filter_by(layout=layout).first()
    ocr = db.query(OCRInvoice).filter_by(layout=layout).first()

    if not gt or not ocr:
        return None

    result = {}

    fields = [
        "issue_date", "sale_date", "payment_due", "currency",
        "seller_name", "seller_address", "seller_nip",
        "buyer_name", "buyer_address", "buyer_nip",
        "order_number", "payment_method", "notes",
        "total_net", "total_vat", "total_gross"
    ]

    for f in fields:
        result[f] = {
            "gt": getattr(gt, f),
            "ocr": getattr(ocr, f),
            "match": getattr(gt, f) == getattr(ocr, f)
        }

    return result
