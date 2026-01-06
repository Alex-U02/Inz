from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import OCRInvoice, OCRItem, OCRRun

def _to_float(value):
    """Konwertuje wartość na float lub zwraca None, jeśli się nie da."""
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).replace(",", ".").strip()
        return float(value)
    except:
        return None


def save_ocr_results(parsed: dict, engine: str, raw_text: str, duration_ms: int):
    db: Session = SessionLocal()

    # Zapis OCRRun
    run = OCRRun(
        invoice_number=parsed.get("invoice_number"),
        engine=engine,
        duration_ms=duration_ms,
        raw_text=raw_text
    )
    db.add(run)
    db.commit()

    # Zapis OCRInvoice
    invoice = OCRInvoice(
        invoice_number=parsed.get("invoice_number"),
        engine=engine,
        issue_date=parsed.get("issue_date"),
        sale_date=parsed.get("sale_date"),
        payment_due=parsed.get("payment_due"),
        currency=parsed.get("currency"),
        seller_name=parsed.get("seller_name"),
        seller_address=parsed.get("seller_address"),
        seller_nip=parsed.get("seller_nip"),
        seller_account=parsed.get("seller_account"),
        seller_regon=parsed.get("seller_regon"),
        buyer_name=parsed.get("buyer_name"),
        buyer_address=parsed.get("buyer_address"),
        buyer_nip=parsed.get("buyer_nip"),
        order_number=parsed.get("order_number"),
        payment_method=parsed.get("payment_method"),
        notes=parsed.get("notes"),
        total_net=_to_float(parsed.get("total_net")),
        total_vat=_to_float(parsed.get("total_vat")),
        total_gross=_to_float(parsed.get("total_gross")),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Zapis pozycji
    for item in parsed.get("items", []):
        db_item = OCRItem(
            ocr_invoice_id=invoice.id,
            name=item.get("name"),
            qty=_to_float(item.get("qty")),
            unit=item.get("unit"),
            price_net=_to_float(item.get("price_net")),
            vat=_to_float(item.get("vat")),
            net=_to_float(item.get("net")),
            gross=_to_float(item.get("gross")),
        )
        db.add(db_item)

    db.commit()
    db.close()


def clear_ocr():
    """Czyści wszystkie dane OCR z bazy."""
    db = SessionLocal()
    db.query(OCRItem).delete()
    db.query(OCRInvoice).delete()
    db.query(OCRRun).delete()
    db.commit()
    db.close()
