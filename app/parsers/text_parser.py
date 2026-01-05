import re
from typing import Optional, Dict

NUMBER = r"\d+(?:[.,]\d+)?"

def _clean_num(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.replace(",", ".").strip()


def _extract(patterns, text: str) -> Optional[str]:
    """Zwraca pierwsze dopasowanie."""
    if isinstance(patterns, str):
        patterns = [patterns]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            groups = [g for g in m.groups() if g]
            if groups:
                return groups[-1].strip()
    return None


def _extract_last(patterns, text: str) -> Optional[str]:
    """Zwraca ostatnie dopasowanie — idealne dla sekcji podsumowania."""
    if isinstance(patterns, str):
        patterns = [patterns]

    for pat in patterns:
        matches = re.findall(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if matches:
            last = matches[-1]
            if isinstance(last, tuple):
                for g in reversed(last):
                    if g:
                        return g.strip()
            else:
                return last.strip()
    return None


# ============================================================
#  GŁÓWNA FUNKCJA PARSERA TEKSTOWEGO
# ============================================================

def parse_text_fields(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Parser tekstowy — wyciąga wszystkie dane spoza tabeli.
    """

    # -------------------------
    # NUMER FAKTURY (najpierw pewne wzorce)
    # -------------------------
    invoice_number = _extract(
        [
            r"(FV\/[0-9]{3,6})",        
            r"(FVI[0-9]{3,6})",         
            r"Nr\s+faktury[:\s]*([A-Z0-9\/\-]+)",
            r"Numer[:\s]*([A-Z0-9\/\-]+)",
            r"Nr[:\s]*([A-Z0-9\/\-]+)",
            r"Faktura\s+VAT.*?([A-Z0-9\/\-]+)",
            r"Faktura\s+nr[:\s]*([A-Z0-9\/\-]+)",
        ],
        raw_text,
    )

    # -------------------------
    # DATY
    # -------------------------
    issue_date = _extract(
        [
            r"Data\s+wystawienia[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Data\s+wstawienia[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Wystawiono[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Wystawienie[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ],
        raw_text,
    )

    sale_date = _extract(
        [
            r"Data\s+sprzedaży[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Sprzedaż[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ],
        raw_text,
    )

    payment_due = _extract(
        r"Termin\s+płatności[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        raw_text,
    )

    # -------------------------
    # NIP / REGON / KONTO
    # -------------------------
    seller_nip = _extract(
        [
            r"SPRZEDAWCA.*?NIP[:\s]*([0-9]{10})",
            r"Sprzedawca.*?NIP[:\s]*([0-9]{10})",
        ],
        raw_text,
    )

    buyer_nip = _extract(
        [
            r"NABYWCA.*?NIP[:\s]*([0-9]{10})",
            r"Nabywca.*?NIP[:\s]*([0-9]{10})",
            r"Nabyca.*?NIP[:\s]*([0-9]{10})",
            r"NABYCA.*?NIP[:\s]*([0-9]{10})",
        ],
        raw_text,
    )

    regon = _extract(r"REGON[:\s]*([0-9]{9})", raw_text)

    order_number = _extract(
        [
            r"Numer\s+zamówienia[:\s]*([A-Z0-9\-\/]+)",
            r"Zamówienie[:\s]*([A-Z0-9\-\/]+)",
        ],
        raw_text,
    )

    seller_account = _extract(
        [
            r"(PL[0-9]{26})",
            r"IBAN[:\s]*([A-Z0-9]{10,})",
        ],
        raw_text,
    )

    # -------------------------
    # NAZWY KONTRAHENTÓW
    # -------------------------
    seller_name = None
    m = re.search(
        r"(SPRZEDAWCA|Sprzedawca)\s+(.*?)\s*?NIP[:]",
        raw_text,
        flags=re.DOTALL,
    )
    if m:
        seller_name = m.group(2).split("\n")[0].strip()

    buyer_name = None
    m = re.search(
        r"(NABYWCA|Nabywca|Nabyca|NABYCA)\s+(.*?)\s*?NIP[:]",
        raw_text,
        flags=re.DOTALL,
    )
    if m:
        buyer_name = m.group(2).split("\n")[0].strip()

    # -------------------------
    # SUMY
    # -------------------------
    total_net = _extract_last(
        [
            rf"Suma\s+netto[:\s]*({NUMBER})",
            rf"Netto[:\s]*({NUMBER})",
        ],
        raw_text,
    )

    total_vat = _extract_last(
        [
            rf"Suma\s+VAT[:\s]*({NUMBER})",
            rf"Suma\s+VAI[:\s]*({NUMBER})", 
            rf"VAT[:\s]*({NUMBER})",
            rf"VAI[:\s]*({NUMBER})",
        ],
        raw_text,
    )

    total_gross = _extract_last(
        [
            rf"Suma\s+brutto[:\s]*({NUMBER})",
            rf"Brutto[:\s]*({NUMBER})",
            rf"Brutto\s*\n\s*({NUMBER})",
        ],
        raw_text,
    )

    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "sale_date": sale_date,
        "payment_due": payment_due,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "seller_nip": seller_nip,
        "buyer_nip": buyer_nip,
        "regon": regon,
        "order_number": order_number,
        "seller_account": seller_account,
        "total_net": _clean_num(total_net),
        "total_vat": _clean_num(total_vat),
        "total_gross": _clean_num(total_gross),
    }
