import re
from typing import Optional, Dict

NUMBER = r"\d+(?:[.,]\d+)?"

def _clean_num(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.replace(",", ".").strip()


def _extract(patterns, text: str) -> Optional[str]:
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


def _extract_name_and_address(raw_text: str, header_patterns):
    if isinstance(header_patterns, str):
        header_patterns = [header_patterns]

    header_regex = "|".join(header_patterns)

    m = re.search(
        rf"(?:{header_regex})\s*(.*?)\n\s*NIP[:\s]*[0-9]{{3,}}",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        block = m.group(1)
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if lines:
            name = lines[0]
            address = " ".join(lines[1:]) if len(lines) > 1 else None
            return name, address

    return None, None


def _extract_buyer_nip(raw_text: str):
    m = re.search(
        r"(NABYWCA|Nabywca|NABYCA|Nabyca)(.*?)(NIP[:\s]*([0-9]{10}))",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(4)
    
    all_nips = re.findall(r"NIP[:\s]*([0-9]{10})", raw_text, re.IGNORECASE)
    if len(all_nips) >= 2:
        return all_nips[1]
    
    return None


def _extract_notes(raw_text: str):
    m = re.search(
        r"Uwagi[:\s]*(.*?)(?:\n\S|$)",
        raw_text,
        flags=re. IGNORECASE | re.DOTALL,
    )
    if not m:
        return None

    notes = m.group(1).strip()

    bad = ["Lp", "Ilość", "Jm", "Cena", "Netto", "Brutto", "VAT"]
    clean = []
    for ln in notes.splitlines():
        if not any(b.lower() in ln.lower() for b in bad):
            clean.append(ln)

    result = " ".join(clean).strip()
    return result if result else None


def parse_text_fields(raw_text: str) -> Dict[str, Optional[str]]:
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

    issue_date = _extract(
        [
            r"Data\s+wystawienia[:\s]*([0-9\-]{10})",
            r"Data\s+wstawienia[:\s]*([0-9\-]{10})",
            r"Wystawiono[:\s]*([0-9\-]{10})",
            r"Wystawienie[:\s]*([0-9\-]{10})",
        ],
        raw_text,
    )

    sale_date = _extract(
        [
            r"Data\s+sprzedaży[:\s]*([0-9\-]{10})",
            r"Sprzedaż[:\s]*([0-9\-]{10})",
        ],
        raw_text,
    )

    payment_due = _extract(
        r"Termin\s+płatności[:\s]*([0-9\-]{10})",
        raw_text,
    )

    currency = _extract(
        [
            r"Waluta[:\s]*([A-Z]{3})",
            r"\bPLN\b",
        ],
        raw_text,
    )

    seller_name, seller_address = _extract_name_and_address(
        raw_text,
        ["SPRZEDAWCA", "Sprzedawca"],
    )

    buyer_name, buyer_address = _extract_name_and_address(
        raw_text,
        ["NABYWCA", "Nabywca", "NABYCA", "Nabyca", "Nabwca", "NABWCA"],
    )

    seller_nip = _extract(
        [
            r"SPRZEDAWCA.*?NIP[:\s]*([0-9]{10})",
            r"Sprzedawca.*?NIP[:\s]*([0-9]{10})",
        ],
        raw_text,
    )

    buyer_nip = _extract_buyer_nip(raw_text)

    seller_regon = _extract(
        [
            r"SPRZEDAWCA.*?REGON[:\s]*([0-9]{9})",
            r"Sprzedawca.*?REGON[:\s]*([0-9]{9})",
            r"REGON[:\s]*([0-9]{9})",
        ],
        raw_text,
    )

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
            r"(P[0-9]{26})",
            r"IBAN[:\s]*([A-Z0-9]{10,})",
        ],
        raw_text,
    )

    payment_method = _extract(
        [
            r"(?:Sposób\s+zapłaty|Forma\s+zapłaty|Płatność)[:\s]*([\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)",
        ],
        raw_text,
    )

    notes = _extract_notes(raw_text)

    vertical_sums = re.search(
        r"(?:^|\n)Netto\s*\n\s*VAT\s*\n\s*Brutto\s*\n\s*"
        r"([0-9.,]+)\s*\n\s*([0-9.,]+)\s*\n\s*([0-9.,]+)",
        raw_text,
        re.IGNORECASE
    )
    
    if vertical_sums:
        total_net = vertical_sums. group(1)
        total_vat = vertical_sums. group(2)
        total_gross = vertical_sums.group(3)
    else:
        total_net = _extract_last(
            [
                r"Suma\s+netto[:\s]*([0-9.,]+)",
                r"Razem\s+netto[:\s]*([0-9.,]+)",
                r"(?:^|\n)Netto[:\s]+([0-9.,]+)",
                r"Wartość\s+netto[:\s]*([0-9.,]+)",
                r"Ogółem\s+netto[:\s]*([0-9.,]+)",
            ],
            raw_text,
        )

        total_vat = _extract_last(
            [
                r"Suma\s+VAT[:\s]*([0-9.,]+)",
                r"(?:^|\n)VAT[:\s]+([0-9.,]+)",
                r"Podatek\s+VAT[:\s]*([0-9.,]+)",
                r"Podatek[:\s]*([0-9.,]+)",
            ],
            raw_text,
        )

        total_gross = _extract_last(
            [
                r"Suma\s+brutto[:\s]*([0-9.,]+)",
                r"Razem\s+brutto[:\s]*([0-9.,]+)",
                r"(?:^|\n)Brutto[:\s]+([0-9.,]+)",
                r"Do\s+zapłaty[:\s]*([0-9.,]+)",
                r"Wartość\s+brutto[:\s]*([0-9.,]+)",
                r"Ogółem\s+brutto[:\s]*([0-9.,]+)",
            ],
            raw_text,
        )

    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "sale_date": sale_date,
        "payment_due": payment_due,
        "currency":  currency,
        "seller_name": seller_name,
        "seller_address": seller_address,
        "seller_nip":  seller_nip,
        "seller_account": seller_account,
        "seller_regon": seller_regon,
        "buyer_name": buyer_name,
        "buyer_address": buyer_address,
        "buyer_nip": buyer_nip,
        "order_number": order_number,
        "payment_method": payment_method,
        "notes": notes,
        "total_net": total_net,
        "total_vat": total_vat,
        "total_gross": total_gross,
    }