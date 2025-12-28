import re

def extract_buyer_name(raw_text: str, buyer_nip: str = None) -> str:
    lines = [l.strip() for l in raw_text.splitlines()]
    # 1. Szukaj nagłówka "Nabywca/Nabyca"
    for i, line in enumerate(lines):
        if re.search(r"Nabywca|Nabyca", line):
            # znajdź pierwszą niepustą linię poniżej
            for j in range(i+1, len(lines)):
                if lines[j]:
                    return lines[j]
    # 2. Fallback: linia przed buyer_nip
    if buyer_nip:
        for i, line in enumerate(lines):
            if buyer_nip in line and i-1 >= 0:
                return lines[i-1]
    return None


def normalize_company_name(name: str) -> str:
    """Prosta normalizacja nazw firm (literówki typu '0.0.' → 'o.o.')"""
    return name.replace("0.0.", "o.o.").replace("Z", "z")

def parse_invoice(raw_text: str) -> dict:
    # Numer faktury
    invoice_number = re.search(r"FV[\/I]\d+", raw_text)
    invoice_number_val = None
    if invoice_number:
        invoice_number_val = invoice_number.group(0).replace("I", "/")

    # Daty
    issue_date = re.search(r"Data wystawienia[:\s]*(\d{4}-\d{2}-\d{2})", raw_text)
    sale_date = re.search(r"Data sprzedaży[:\s]*(\d{4}-\d{2}-\d{2})", raw_text)
    payment_due = re.search(r"Termin płatności[:\s]*(\d{4}-\d{2}-\d{2})", raw_text)

    # NIP-y
    nips = re.findall(r"\b\d{10}\b", raw_text)
    seller_nip = nips[0] if len(nips) > 0 else None
    buyer_nip = nips[1] if len(nips) > 1 else None

    # Sprzedawca
    seller_match = re.search(r"Sprzedawca\s+([^\n]+)", raw_text)
    seller_name = normalize_company_name(seller_match.group(1).strip()) if seller_match else None

    # Nabywca
    buyer_name = extract_buyer_name(raw_text, buyer_nip)

    # Kwoty
    total_net = re.search(r"Suma netto\s*([\d,\.]+)", raw_text)
    total_vat = re.search(r"Suma VAT\s*([\d,\.]+)", raw_text)
    total_gross = re.search(r"(Suma brutto|Brutto)\s*([\d,\.]+)", raw_text)

    # Numer zamówienia
    order_number = re.search(r"ORD-\d+", raw_text)

    # Numer rachunku / IBAN
    account_match = re.search(r"PL\d{26}", raw_text)

    # REGON
    regon = re.search(r"REGON[:\s]*(\d+)", raw_text)

    return {
        "invoice_number": invoice_number_val,
        "issue_date": issue_date.group(1) if issue_date else None,
        "sale_date": sale_date.group(1) if sale_date else None,
        "payment_due": payment_due.group(1) if payment_due else None,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "seller_nip": seller_nip,
        "buyer_nip": buyer_nip,
        "regon": regon.group(1) if regon else None,
        "order_number": order_number.group(0) if order_number else None,
        "total_net": total_net.group(1) if total_net else None,
        "total_vat": total_vat.group(1) if total_vat else None,
        "total_gross": total_gross.group(2) if total_gross else None,
        "seller_account": account_match.group(0) if account_match else None
    }
