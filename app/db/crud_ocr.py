from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import OCRInvoice, OCRItem, OCRRun
from sqlalchemy import text

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


def save_ocr_results(parsed: dict, engine: str, raw_text: str, duration_ms: int, layout: str):
    db: Session = SessionLocal()

    # Zapis OCRRun
    run = OCRRun(
        invoice_number=parsed.get("invoice_number"),
        engine=engine,
        duration_ms=duration_ms,
        raw_text=raw_text,
        layout=layout
    )
    db.add(run)
    db.commit()

    # Zapis OCRInvoice
    invoice = OCRInvoice(
        invoice_number=parsed.get("invoice_number"),
        engine=engine,
        layout=layout,
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
    db = SessionLocal()
    db.query(OCRItem).delete()
    db.query(OCRInvoice).delete()
    db.query(OCRRun).delete()
    try:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='ocr_items'"))
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='ocr_invoices'"))
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='ocr_runs'"))
    except:
        pass
    db.commit()
    db.close()
