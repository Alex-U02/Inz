from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class GroundTruthInvoice(Base):
    __tablename__ = "ground_truth_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, index=True)
    layout = Column(String, index=True)
    issue_date = Column(String)
    sale_date = Column(String)
    payment_due = Column(String)
    currency = Column(String)

    seller_name = Column(String)
    seller_address = Column(String)
    seller_nip = Column(String)
    seller_account = Column(String)
    seller_regon = Column(String)

    buyer_name = Column(String)
    buyer_address = Column(String)
    buyer_nip = Column(String)

    order_number = Column(String)
    payment_method = Column(String)
    notes = Column(Text)

    total_net = Column(Float)
    total_vat = Column(Float)
    total_gross = Column(Float)

    items = relationship("GroundTruthItem", back_populates="invoice")


class GroundTruthItem(Base):
    __tablename__ = "ground_truth_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("ground_truth_invoices.id"))

    name = Column(String)
    qty = Column(Float)
    unit = Column(String)
    price_net = Column(Float)
    vat = Column(Float)
    net = Column(Float)
    gross = Column(Float)

    invoice = relationship("GroundTruthInvoice", back_populates="items")


class OCRInvoice(Base):
    __tablename__ = "ocr_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, index=True)
    engine = Column(String)
    layout = Column(String, index=True)
    issue_date = Column(String)
    sale_date = Column(String)
    payment_due = Column(String)
    currency = Column(String)

    seller_name = Column(String)
    seller_address = Column(String)
    seller_nip = Column(String)
    seller_account = Column(String)
    seller_regon = Column(String)

    buyer_name = Column(String)
    buyer_address = Column(String)
    buyer_nip = Column(String)

    order_number = Column(String)
    payment_method = Column(String)
    notes = Column(Text)

    total_net = Column(Float)
    total_vat = Column(Float)
    total_gross = Column(Float)

    items = relationship("OCRItem", back_populates="invoice")


class OCRItem(Base):
    __tablename__ = "ocr_items"

    id = Column(Integer, primary_key=True, index=True)
    ocr_invoice_id = Column(Integer, ForeignKey("ocr_invoices.id"))

    name = Column(String)
    qty = Column(Float)
    unit = Column(String)
    price_net = Column(Float)
    vat = Column(Float)
    net = Column(Float)
    gross = Column(Float)

    invoice = relationship("OCRInvoice", back_populates="items")


class OCRRun(Base):
    __tablename__ = "ocr_runs"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String)
    engine = Column(String)
    layout = Column(String, index=True)
    duration_ms = Column(Integer)
    raw_text = Column(Text)
