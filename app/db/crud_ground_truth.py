from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import GroundTruthInvoice, GroundTruthItem
from sqlalchemy import text

def clear_ground_truth():
    db = SessionLocal()
    db.query(GroundTruthItem).delete()
    db.query(GroundTruthInvoice).delete()
    try:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='ground_truth_items'"))
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='ground_truth_invoices'"))
    except:
        pass
    db.commit()
    db.close()


def save_ground_truth(payload: dict, layout: str):
    db: Session = SessionLocal()

    invoice = GroundTruthInvoice(
        invoice_number=payload["invoice_number"],
        layout=layout,
        issue_date=payload["issue_date"],
        sale_date=payload["sale_date"],
        payment_due=payload["payment_due"],
        currency=payload["currency"],
        seller_name=payload["seller_name"],
        seller_address=payload["seller_address"],
        seller_nip=payload["seller_nip"],
        seller_account=payload["seller_account"],
        seller_regon=payload["seller_regon"],
        buyer_name=payload["buyer_name"],
        buyer_address=payload["buyer_address"],
        buyer_nip=payload["buyer_nip"],
        order_number=payload["order_number"],
        payment_method=payload["payment_method"],
        notes=payload["notes"],
        total_net=payload["total_net"],
        total_vat=payload["total_vat"],
        total_gross=payload["total_gross"]
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    for item in payload["items"]:
        db_item = GroundTruthItem(
            invoice_id=invoice.id,
            name=item["name"],
            qty=item["qty"],
            unit=item["unit"],
            price_net=item["price_net"],
            vat=item["vat"],
            net=item["net"],
            gross=item["gross"]
        )
        db.add(db_item)

    db.commit()
    db.close()
