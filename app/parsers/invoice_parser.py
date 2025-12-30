import re
from typing import Any, Dict, List, Optional


NUMBER = r"\d+(?:[.,]\d+)?"
NUM_RE = re.compile(NUMBER)


# -----------------------------
#  UTILS
# -----------------------------

def _clean_num(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.replace(",", ".").strip()


def _normalize_spaces(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


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


def _is_summary_line(line: str) -> bool:
    l = line.lower()
    return any(
        k in l
        for k in ["suma netto", "suma vat", "suma brutto", "netto", "vat", "brutto"]
    )


def _is_header_hint(line: str) -> bool:
    l = line.lower()
    return any(
        k in l
        for k in [
            "lp.",
            "lp ",
            "nr pozycja",
            "nazwa towaru",
            "nazwa towarulusługi",
            "nazwa",
            "pozycja",
            "opis",
            "ilość",
            "ilosc",
            "jm",
            "j.m",
            "cena netto",
            "wartość netto",
            "wartość brutto",
            "netto",
            "brutto",
        ]
    )


# -----------------------------
#  HEADER FIELDS
# -----------------------------

def _extract_header(text: str) -> Dict[str, Optional[str]]:
    invoice_number = _extract(
        [
            r"Nr\s+faktury[:\s]*([A-Z0-9\/\-]+)",
            r"Faktura\s+VAT.*?([A-Z0-9\/\-]+)",
            r"Faktura\s+nr[:\s]*([A-Z0-9\/\-]+)",
            r"Numer[:\s]*([A-Z0-9\/\-]+)",
            r"Nr[:\s]*([A-Z0-9\/\-]+)",
        ],
        text,
    )

    issue_date = _extract(
        [
            r"Data\s+wystawienia[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Wystawiono[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Wystawienie[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ],
        text,
    )

    sale_date = _extract(
        [
            r"Data\s+sprzedaży[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Sprzedaż[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ],
        text,
    )

    payment_due = _extract(
        r"Termin\s+płatności[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        text,
    )

    seller_nip = _extract(
        [
            r"SPRZEDAWCA.*?NIP[:\s]*([0-9]{10})",
            r"Sprzedawca.*?NIP[:\s]*([0-9]{10})",
        ],
        text,
    )
    buyer_nip = _extract(
        [
            r"NABYWCA.*?NIP[:\s]*([0-9]{10})",
            r"Nabywca.*?NIP[:\s]*([0-9]{10})",
            r"Nabyca.*?NIP[:\s]*([0-9]{10})",
        ],
        text,
    )

    regon = _extract(r"REGON[:\s]*([0-9]{9})", text)

    order_number = _extract(
        [
            r"Numer\s+zamówienia[:\s]*([A-Z0-9\-\/]+)",
            r"Zamówienie[:\s]*([A-Z0-9\-\/]+)",
        ],
        text,
    )

    seller_account = _extract(
        [
            r"(PL[0-9]{26})",
            r"IBAN[:\s]*([A-Z0-9]{10,})",
        ],
        text,
    )

    seller_name = None
    m = re.search(
        r"(SPRZEDAWCA|Sprzedawca)\s+(.*?)\s+NIP[:]",
        text,
        flags=re.DOTALL,
    )
    if m:
        block = m.group(2)
        seller_name = _normalize_spaces(block.split("\n")[0])

    buyer_name = None
    m = re.search(
        r"(NABYWCA|Nabywca|Nabyca)\s+(.*?)\s+NIP[:]",
        text,
        flags=re.DOTALL,
    )
    if m:
        block = m.group(2)
        buyer_name = _normalize_spaces(block.split("\n")[0])

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
    }


# -----------------------------
#  TOTALS
# -----------------------------

def _extract_totals(text: str) -> Dict[str, Optional[str]]:
    total_net = _extract(
        [rf"Suma\s+netto\s*({NUMBER})", rf"Netto[:\s]*({NUMBER})"],
        text,
    )
    total_vat = _extract(
        [rf"Suma\s+VAT\s*({NUMBER})", rf"VAT[:\s]*({NUMBER})"],
        text,
    )
    total_gross = _extract(
        [rf"Suma\s+brutto\s*({NUMBER})", rf"Brutto[:\s]*({NUMBER})"],
        text,
    )

    return {
        "total_net": _clean_num(total_net),
        "total_vat": _clean_num(total_vat),
        "total_gross": _clean_num(total_gross),
    }


# -----------------------------
#  TABLE REGION
# -----------------------------

def _find_table_start(lines: List[str]) -> Optional[int]:
    # 1) klasyczne "Lp." / "Nr Pozycja"
    for i, line in enumerate(lines):
        l = line.lower()
        if "lp." in l or l.startswith("lp ") or "nr pozycja" in l:
            return i + 1

    # 2) linia z wieloma słowami nagłówkowymi
    for i, line in enumerate(lines):
        if _is_header_hint(line):
            return i + 1

    return None


# -----------------------------
#  ITEM PARSER (STATE MACHINE)
# -----------------------------

def _parse_items_from_lines(lines: List[str], start_idx: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    name_buf: List[str] = []
    num_buf: List[str] = []
    in_item = False

    def flush():
        nonlocal name_buf, num_buf, items, in_item
        if not name_buf and not num_buf:
            return

        name = _normalize_spaces(" ".join(name_buf)) if name_buf else None

        qty = price_net = vat = net = gross = None
        nums = [_clean_num(n) for n in num_buf]

        if len(nums) >= 1:
            qty = nums[0]
        if len(nums) >= 2:
            price_net = nums[1]
        if len(nums) >= 3:
            vat = nums[2]
        if len(nums) >= 4:
            net = nums[3]
        if len(nums) >= 5:
            gross = nums[4]

        items.append(
            {
                "name": name,
                "qty": qty,
                "unit": None,  # jednostek nie zgadujemy
                "price_net": price_net,
                "vat": vat,
                "net": net,
                "gross": gross,
            }
        )

        name_buf = []
        num_buf = []
        in_item = False

    def lookahead_text(i: int) -> Optional[str]:
        for j in range(i + 1, len(lines)):
            t = lines[j].strip()
            if t:
                return t
        return None

    for i in range(start_idx, len(lines)):
        raw = lines[i]
        line = raw.strip()
        if not line:
            continue
        if _is_summary_line(line):
            flush()
            break

        nums = NUM_RE.findall(line)
        text_only = NUM_RE.sub(" ", line).strip()
        has_text = any(ch.isalpha() for ch in text_only)
        is_pure_num = bool(nums) and not has_text

        # kandydat na numer pozycji (Lp.): np. "1", "2", "3"
        is_lp_candidate = False
        if is_pure_num:
            try:
                v = int(nums[0].split(",")[0].split(".")[0])
                # rozsądne ograniczenie – Lp. nie będzie 350
                if 1 <= v <= 50:
                    nxt = lookahead_text(i)
                    if nxt and not _is_summary_line(nxt):
                        # następna linia z tekstem → traktuj jako początek pozycji
                        is_lp_candidate = True
            except ValueError:
                pass

        if is_lp_candidate:
            # numer pozycji – zamyka poprzednią pozycję, nową zaczniemy od kolejnej linii
            flush()
            in_item = False
            continue

        if has_text and not nums:
            # czysty tekst – nazwa lub dalszy opis
            if not in_item:
                in_item = True
            name_buf.append(text_only)
        elif nums and not has_text:
            # czyste liczby – dane liczbowe bieżącej pozycji
            if in_item:
                num_buf.extend(nums)
        elif nums and has_text:
            # linia mieszana (typowy wiersz Tesseracta)
            if in_item and (name_buf or num_buf):
                flush()
            in_item = True
            name_buf.append(text_only)
            num_buf.extend(nums)
        else:
            flush()

    flush()
    return items


# -----------------------------
#  MAIN
# -----------------------------

def parse_invoice(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {
            "invoice_number": None,
            "issue_date": None,
            "sale_date": None,
            "payment_due": None,
            "seller_name": None,
            "buyer_name": None,
            "seller_nip": None,
            "buyer_nip": None,
            "regon": None,
            "order_number": None,
            "seller_account": None,
            "total_net": None,
            "total_vat": None,
            "total_gross": None,
            "items": [],
        }

    lines = raw_text.splitlines()

    header = _extract_header(raw_text)
    totals = _extract_totals(raw_text)

    start_idx = _find_table_start(lines)
    if start_idx is not None:
        items = _parse_items_from_lines(lines, start_idx)
    else:
        items = []

    return {
        **header,
        **totals,
        "items": items,
    }
