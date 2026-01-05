import re
from typing import List, Dict, Optional
from collections import defaultdict

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

SUMMARY_WORDS = {"suma", "netto", "vat", "brutto", "razem", "uwagi", "forma zapłaty", "sposób zapłaty"}


def is_number(t: str) -> bool:
    return bool(NUMBER.fullmatch(t.replace(",", ".")))


def norm_num(t: Optional[str]) -> Optional[str]:
    if t is None:
        return None
    return t.replace(",", ".").strip()


def is_summary_text(t: str) -> bool:
    tl = t.lower()
    return any(w in tl for w in SUMMARY_WORDS)


# -----------------------
# BLOKOWE WIERSZE (Y-CENTERS)
# -----------------------

def group_rows(words: List[Dict], row_tolerance: float = 16.0) -> List[List[Dict]]:
    """
    Blokowe grupowanie wierszy:
    - używa środka pionowego słowa: y_center = y + h/2
    - przypisuje słowo do najbliższego istniejącego wiersza, jeśli dystans w Y <= row_tolerance
    - w przeciwnym razie tworzy nowy wiersz
    """
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: (w.get("y", 0.0), w.get("x", 0.0)))

    row_centers: List[float] = []
    rows: List[List[Dict]] = []

    for w in words_sorted:
        y = w.get("y", 0.0)
        h = w.get("h", 0.0)
        y_center = y + h / 2.0

        best_idx = None
        best_dist = None

        for i, rc in enumerate(row_centers):
            dist = abs(y_center - rc)
            if dist <= row_tolerance and (best_dist is None or dist < best_dist):
                best_idx = i
                best_dist = dist

        if best_idx is None:
            row_centers.append(y_center)
            rows.append([w])
        else:
            rows[best_idx].append(w)
            row_centers[best_idx] = (row_centers[best_idx] + y_center) / 2.0

    # sortujemy słowa w wierszach po X
    for r in rows:
        r.sort(key=lambda ww: ww.get("x", 0.0))

    # sortujemy wiersze po ich Y-center
    rows_with_centers = []
    for r in rows:
        ys = [ww.get("y", 0.0) + ww.get("h", 0.0) / 2.0 for ww in r]
        center = sum(ys) / len(ys) if ys else 0.0
        rows_with_centers.append((center, r))
    rows_with_centers.sort(key=lambda t: t[0])

    return [r for _, r in rows_with_centers]


# -----------------------
# WYKRYWANIE NAGŁÓWKA
# -----------------------

HEADER_KEYWORDS = {
    "ilość", "ilosc",
    "j.m", "j.m.", "jm",
    "cena", "netto",
    "brutto", "vat", "stawka",
    "nazwa", "pozycja", "opis", "towaru", "usługi", "uslugi",
}


def detect_header_candidates(rows: List[List[Dict]]) -> List[int]:
    """
    Zwraca indeksy wierszy, które wyglądają jak nagłówki:
    - zawierają co najmniej 2 słowa z HEADER_KEYWORDS
    """
    candidates = []
    for i, row in enumerate(rows):
        texts = " ".join(w["text"].lower() for w in row)
        score = sum(1 for kw in HEADER_KEYWORDS if kw in texts)
        if score >= 2:
            candidates.append(i)
    return candidates


def count_numeric_rows_below(rows: List[List[Dict]], start_idx: int, max_lookahead: int = 6) -> int:
    """
    Liczy, ile wierszy poniżej (w zasięgu kilku wierszy) zawiera liczby.
    Używane do walidacji, że pod nagłówkiem faktycznie zaczyna się tabela.
    """
    count = 0
    end = min(len(rows), start_idx + 1 + max_lookahead)
    for i in range(start_idx + 1, end):
        row = rows[i]
        text = " ".join(w["text"] for w in row)
        if any(is_number(tok) for tok in text.replace(",", ".").split()):
            count += 1
    return count


def detect_header_row(rows: List[List[Dict]]) -> Optional[int]:
    """
    Wykrywa wiersz nagłówka tabeli w sposób odporny na layouty:
    1. Szuka kandydatów po słowach kluczowych (HEADERS).
    2. Wybiera taki, który:
       - ma największą szerokość X,
       - ma pod sobą co najmniej 2 wiersze z liczbami.
    """
    candidates = detect_header_candidates(rows)
    if not candidates:
        return None

    best_idx = None
    best_score = None

    for idx in candidates:
        row = rows[idx]
        xs = [w.get("x", 0.0) for w in row]
        ws = [w.get("w", 0.0) for w in row]
        if not xs:
            continue
        x_min = min(xs)
        x_max = max(x + w for x, w in zip(xs, ws))
        width = x_max - x_min

        numeric_below = count_numeric_rows_below(rows, idx, max_lookahead=6)

        score = width + numeric_below * 1000.0

        if best_score is None or score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


# -----------------------
# KOLUMNY Z NAGŁÓWKA
# -----------------------

def classify_header_text(txt: str) -> Optional[str]:
    t = txt.lower()

    if "lp" in t or "nr" in t:
        return "lp"
    if "nazwa" in t or "pozycja" in t or "opis" in t or "towaru" in t or "usługi" in t or "uslugi" in t:
        return "name"
    if "ilo" in t:
        return "qty"
    if "j.m" in t or "jm" in t:
        return "unit"
    if "cena" in t and "netto" in t:
        return "price_net"
    if t.strip() == "cena":
        return "price_net"
    if "vat" in t:
        return "vat"
    if "netto" in t:
        return "net"
    if "brutto" in t:
        return "gross"

    return None


def build_column_model(header_row: List[Dict]) -> List[Dict]:
    """
    Buduje model kolumn na podstawie nagłówka:
    - bierze środki X słów nagłówkowych,
    - sortuje po X,
    - granice między kolumnami = połowa odległości między środkami.
    """
    headers = []
    for w in header_row:
        col_type = classify_header_text(w["text"])
        if col_type is None:
            continue
        x_center = w.get("x", 0.0) + w.get("w", 0.0) / 2.0
        headers.append((x_center, col_type))

    headers.sort(key=lambda h: h[0])

    columns = []
    for i, (x_center, col_type) in enumerate(headers):
        if i == 0:
            left = x_center - 350.0
        else:
            prev_center = headers[i - 1][0]
            left = (prev_center + x_center) / 2.0

        if i == len(headers) - 1:
            right = x_center + 350.0
        else:
            next_center = headers[i + 1][0]
            right = (x_center + next_center) / 2.0

        columns.append({
            "type": col_type,
            "x_min": left,
            "x_max": right,
        })

    return columns


def assign_cells_to_columns(row: List[Dict], columns: List[Dict]) -> Dict[str, List[Dict]]:
    cells_by_type: Dict[str, List[Dict]] = defaultdict(list)

    for w in row:
        x_center = w.get("x", 0.0) + w.get("w", 0.0) / 2.0
        assigned_type = None
        for col in columns:
            if col["x_min"] <= x_center <= col["x_max"]:
                assigned_type = col["type"]
                break
        if assigned_type is not None:
            cells_by_type[assigned_type].append(w)

    return cells_by_type


def join_text(cells: List[Dict]) -> str:
    parts = [w["text"] for w in sorted(cells, key=lambda ww: ww.get("x", 0.0))]
    return " ".join(parts).strip()


# -----------------------
# GŁÓWNY PARSER
# -----------------------

def parse_table_fields(words: List[Dict], debug: bool = False):
    """
    Główny parser:
    - blokowe grupowanie wierszy po Y,
    - wykrywanie nagłówka odporne na layouty,
    - budowa modelu kolumn z nagłówka,
    - przypisanie słów do kolumn,
    - łączenie multi-row nazw,
    - odcięcie podsumowań.
    """
    rows = group_rows(words, row_tolerance=10.0)

    header_idx = detect_header_row(rows)
    if header_idx is None:
        return [], {"error": "header_not_found", "rows": rows}

    header_row = rows[header_idx]
    columns = build_column_model(header_row)

    items: List[Dict[str, Optional[str]]] = []
    current_item: Optional[Dict[str, Optional[str]]] = None

    debug_rows = []

    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        row_text = " ".join(w["text"] for w in row)

        if is_summary_text(row_text):
            break

        cells_by_type = assign_cells_to_columns(row, columns)

        debug_rows.append({
            "row_index": i,
            "row_text": row_text,
            "cells_by_type": {k: [c["text"] for c in v] for k, v in cells_by_type.items()}
        })

        name_text = join_text(cells_by_type.get("name", [])) if "name" in cells_by_type else ""
        qty_text = join_text(cells_by_type.get("qty", [])) if "qty" in cells_by_type else ""
        unit_text = join_text(cells_by_type.get("unit", [])) if "unit" in cells_by_type else ""
        price_text = join_text(cells_by_type.get("price_net", [])) if "price_net" in cells_by_type else ""
        vat_text = join_text(cells_by_type.get("vat", [])) if "vat" in cells_by_type else ""
        net_text = join_text(cells_by_type.get("net", [])) if "net" in cells_by_type else ""
        gross_text = join_text(cells_by_type.get("gross", [])) if "gross" in cells_by_type else ""

        has_any_number = any([
            is_number(qty_text) if qty_text else False,
            is_number(price_text) if price_text else False,
            is_number(net_text) if net_text else False,
            is_number(gross_text) if gross_text else False,
        ])

        only_name = bool(name_text) and not has_any_number

        # Kontynuacja nazwy: wiersz z samą nazwą, bez liczb
        if only_name and current_item is not None:
            base_name = current_item["name"] or ""
            current_item["name"] = (base_name + " " + name_text).strip()
            continue

        # Kontynuacja pozycji: unit/vat w osobnym wierszu, bez name i bez price/net/gross
        if current_item is not None:
            if not name_text and not price_text and not net_text and not gross_text:
                if unit_text:
                    current_item["unit"] = unit_text
                if vat_text:
                    current_item["vat"] = vat_text
                continue

        # Wiersz zupełnie pusty / śmieciowy
        if not has_any_number and not name_text:
            continue

        # Nowa pozycja
        item: Dict[str, Optional[str]] = {
            "name": name_text.strip() if name_text else None,
            "qty": qty_text if qty_text else None,
            "unit": unit_text if unit_text else None,
            "price_net": norm_num(price_text) if price_text else None,
            "vat": vat_text.strip() if vat_text else None,
            "net": norm_num(net_text) if net_text else None,
            "gross": norm_num(gross_text) if gross_text else None,
        }

        items.append(item)
        current_item = item

    debug_info = {
        "rows": rows,
        "header_idx": header_idx,
        "columns": columns,
        "assigned_rows": debug_rows
    }

    return items, debug_info
