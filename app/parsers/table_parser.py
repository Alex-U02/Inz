import re
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

SUMMARY_WORDS = {
    "suma", "netto", "vat", "brutto", "razem",
    "uwagi", "forma zapłaty", "sposób zapłaty", "sposob zaplaty"
}

def is_number(t: str) -> bool:
    """Sprawdza czy tekst to liczba"""
    return bool(NUMBER.fullmatch(t. replace(",", ".")))

def norm_num(t: Optional[str]) -> Optional[str]:
    """Normalizuje liczbę (zamienia przecinek na kropkę)"""
    if t is None:
        return None
    return t.replace(",", ".").strip()

def is_summary_text(t: str) -> bool:
    """Sprawdza czy wiersz to podsumowanie"""
    tl = t.lower()
    return any(w in tl for w in SUMMARY_WORDS)


# ============================================================
# GRUPOWANIE WIERSZY
# ============================================================

def group_rows(words: List[Dict], row_tolerance: float = 10.0) -> List[List[Dict]]:
    """
    Grupuje słowa w wiersze na podstawie pozycji Y. 
    Używa bardziej restrykcyjnego progu 10px zamiast 14px.
    """
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: (w. get("y", 0.0), w.get("x", 0.0)))

    row_centers = []
    rows = []

    for w in words_sorted:
        y_center = w["y"] + w["h"] / 2
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
            row_centers[best_idx] = (row_centers[best_idx] + y_center) / 2

    # Sortowanie słów w wierszach po X
    for r in rows:
        r.sort(key=lambda ww: ww["x"])

    # Sortowanie wierszy po Y
    rows_with_centers = []
    for r in rows:
        centers = [w["y"] + w["h"] / 2 for w in r]
        rows_with_centers.append((sum(centers) / len(centers), r))

    rows_with_centers.sort(key=lambda t: t[0])
    return [r for _, r in rows_with_centers]


# ============================================================
# WYKRYWANIE NAGŁÓWKA
# ============================================================

HEADER_KEYWORDS = {
    "ilość", "ilosc", "jm", "j.m", "j.m.",
    "cena", "netto", "brutto", "vat", "stawka",
    "nazwa", "pozycja", "opis", "towaru", "usługi", "uslugi",
    "wartość", "wartosc"
}

def detect_header_candidates(rows: List[List[Dict]]) -> List[int]:
    """Znajduje wiersze które mogą być nagłówkiem (mają >=2 słowa kluczowe)"""
    out = []
    for i, row in enumerate(rows):
        text = " ".join(w["text"].lower() for w in row)
        score = sum(1 for kw in HEADER_KEYWORDS if kw in text)
        if score >= 2:
            out.append(i)
    return out

def count_numeric_rows_below(rows: List[List[Dict]], start_idx: int, max_lookahead: int = 6) -> int:
    """Liczy ile wierszy poniżej ma liczby (sugeruje że to dane)"""
    count = 0
    end = min(len(rows), start_idx + 1 + max_lookahead)
    for i in range(start_idx + 1, end):
        text = " ".join(w["text"] for w in rows[i])
        if any(is_number(tok) for tok in text.replace(",", ".").split()):
            count += 1
    return count

def detect_header_row(rows: List[List[Dict]]) -> Optional[int]:
    """
    Wykrywa wiersz nagłówka tabeli.
    Preferuje nagłówki które: 
    - Mają wiele słów kluczowych
    - Są szerokie (zajmują dużo miejsca w poziomie)
    - Mają wiele liczbowych wierszy poniżej
    """
    candidates = detect_header_candidates(rows)
    if not candidates: 
        return None

    best_idx = None
    best_score = None

    for idx in candidates:
        row = rows[idx]
        xs = [w["x"] for w in row]
        ws = [w["w"] for w in row]
        if not xs: 
            continue

        x_min = min(xs)
        x_max = max(x + w for x, w in zip(xs, ws))
        width = x_max - x_min

        numeric_below = count_numeric_rows_below(rows, idx)
        
        # Scoring:  szerokość + bonus za liczbowe wiersze poniżej
        score = width + numeric_below * 1000

        if best_score is None or score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


# ============================================================
# MODEL KOLUMN
# ============================================================

def classify_header_text(txt: str) -> Optional[str]:
    """Klasyfikuje tekst nagłówka do typu kolumny"""
    t = txt.lower()

    if "lp" in t or t.strip() == "nr":
        return "lp"
    if any(k in t for k in ["nazwa", "pozycja", "opis", "towaru", "usługi", "uslugi"]):
        return "name"
    if "ilo" in t: 
        return "qty"
    if "j.m" in t or "jm" in t:
        return "unit"
    if "cena" in t and "netto" in t: 
        return "price_net"
    if t.strip() == "cena":
        return "price_net"
    if "vat" in t and "stawka" not in t:
        return "vat"
    if "stawka" in t and "vat" in t:
        return "vat"
    if "netto" in t and "cena" not in t:
        return "net"
    if "brutto" in t: 
        return "gross"

    return None


def build_column_model(header_row: List[Dict]) -> List[Dict]:
    """
    Buduje model kolumn na podstawie nagłówka.
    POPRAWKA: Granice kolumn jako punkty między środkami nagłówków,
    nie nachodzące zakresy.
    """
    headers = []
    for w in header_row:
        col_type = classify_header_text(w["text"])
        if col_type:
            x_center = w["x"] + w["w"] / 2
            headers.append((x_center, col_type))

    if not headers:
        return []

    headers.sort(key=lambda h: h[0])

    columns = []
    for i, (xc, col_type) in enumerate(headers):
        # Lewa granica:  połowa odległości do poprzedniego nagłówka
        # (albo xc - 300 jeśli to pierwsza kolumna)
        if i == 0:
            left = xc - 300
        else:
            left = (headers[i - 1][0] + xc) / 2

        # Prawa granica: połowa odległości do następnego nagłówka
        # (albo xc + 300 jeśli to ostatnia kolumna)
        if i == len(headers) - 1:
            right = xc + 300
        else:
            right = (xc + headers[i + 1][0]) / 2

        columns.append({
            "type": col_type,
            "x_min": left,
            "x_max": right,
            "x_center": xc
        })

    return columns


def assign_cells_to_columns(row: List[Dict], columns: List[Dict]) -> Dict[str, List[Dict]]: 
    """
    Przypisuje słowa z wiersza do kolumn.
    POPRAWKA: Sprawdza czy środek słowa (nie początek!) jest w zakresie kolumny. 
    """
    out = defaultdict(list)
    for w in row:
        x_center = w["x"] + w["w"] / 2  # POPRAWKA: używamy środka słowa
        
        best_col = None
        best_dist = None
        
        for col in columns:
            if col["x_min"] <= x_center <= col["x_max"]:
                # Priorytet: jeśli w zakresie, to bierz najbliższy centrum kolumny
                dist = abs(x_center - col["x_center"])
                if best_dist is None or dist < best_dist:
                    best_col = col
                    best_dist = dist
        
        if best_col:
            out[best_col["type"]].append(w)

    return out


def join_text(cells: List[Dict]) -> str:
    """Łączy tekst z wielu komórek w jedną wartość"""
    return " ".join(w["text"] for w in sorted(cells, key=lambda ww: ww["x"])).strip()


# ============================================================
# HEURYSTYKI
# ============================================================

def fix_qty_in_unit(qty: str, unit: str) -> Tuple[str, str]:
    """
    HEURYSTYKA: jeśli unit zawiera liczbę → liczba to qty
    Przykład: qty="", unit="8 godz" → qty="8", unit="godz"
    """
    if unit and any(ch.isdigit() for ch in unit) and not qty:
        parts = unit.split()
        nums = [p for p in parts if p.replace(",", ".").replace(".", "").isdigit()]
        if nums:
            qty = nums[0]
            unit = " ".join(p for p in parts if p not in nums)
    return qty, unit


def infer_qty_from_price_net(qty: str, price:  str, net: str) -> str:
    """
    HEURYSTYKA: jeśli net = price * qty → wylicz qty
    Przykład: price="100", net="300" → qty="3"
    """
    if not qty and price and net:
        try:
            p = float(price.replace(",", "."))
            n = float(net.replace(",", "."))
            if p > 0:
                calculated_qty = n / p
                # Sprawdź czy to liczba całkowita (z tolerancją)
                if abs(calculated_qty - round(calculated_qty)) < 0.01:
                    return str(int(round(calculated_qty)))
        except:
            pass
    return qty


def has_any_numeric_value(cells_dict: Dict[str, List[Dict]]) -> bool:
    """Sprawdza czy wiersz ma jakąkolwiek wartość liczbową"""
    for key in ["qty", "price_net", "vat", "net", "gross"]:
        text = join_text(cells_dict. get(key, []))
        if text and any(is_number(tok) for tok in text.split()):
            return True
    return False


# ============================================================
# GŁÓWNY PARSER TABELI
# ============================================================

def parse_table_fields(words: List[Dict], debug: bool = False) -> Tuple[List[Dict], Dict]:
    """
    Główna funkcja parsująca tabelę pozycji faktury.
    
    Returns:
        (items, debug_info)
        - items: lista pozycji faktury
        - debug_info:  informacje debugowania
    """
    
    # 1. Grupowanie słów w wiersze
    rows = group_rows(words, row_tolerance=10.0)
    
    if debug:
        print(f"[DEBUG] Znaleziono {len(rows)} wierszy")

    # 2. Wykrywanie nagłówka
    header_idx = detect_header_row(rows)
    if header_idx is None:
        return [], {
            "error": "header_not_found",
            "rows_count": len(rows),
            "rows": rows if debug else []
        }
    
    if debug:
        print(f"[DEBUG] Nagłówek w wierszu {header_idx}")
        print(f"[DEBUG] Nagłówek: {' | '.join(w['text'] for w in rows[header_idx])}")

    # 3. Budowanie modelu kolumn
    header_row = rows[header_idx]
    columns = build_column_model(header_row)
    
    if not columns:
        return [], {
            "error": "no_columns_detected",
            "header_idx": header_idx,
            "header_text": " ".join(w["text"] for w in header_row)
        }
    
    if debug:
        print(f"[DEBUG] Wykryto {len(columns)} kolumn:")
        for col in columns: 
            print(f"  - {col['type']}: x=[{col['x_min']:. 0f}, {col['x_max']:. 0f}]")

    # 4. Parsowanie wierszy danych
    items = []
    current_item = None
    debug_rows_data = []

    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        row_text = " ".join(w["text"] for w in row)

        # Pomijanie wierszy podsumowania
        if is_summary_text(row_text):
            if debug:
                print(f"[DEBUG] Wiersz {i} to podsumowanie, przerywam")
            break

        # Przypisanie słów do kolumn
        cells = assign_cells_to_columns(row, columns)

        # Wyciągnięcie wartości
        name = join_text(cells.get("name", []))
        qty = join_text(cells.get("qty", []))
        unit = join_text(cells.get("unit", []))
        price = join_text(cells.get("price_net", []))
        vat = join_text(cells.get("vat", []))
        net = join_text(cells.get("net", []))
        gross = join_text(cells.get("gross", []))

        # HEURYSTYKA 1: Popraw qty jeśli jest w kolumnie unit
        qty, unit = fix_qty_in_unit(qty, unit)

        # HEURYSTYKA 2: Wylicz qty jeśli brak
        qty = infer_qty_from_price_net(qty, price, net)

        # Sprawdzenie czy wiersz ma wartości liczbowe
        has_numbers = has_any_numeric_value(cells)

        if debug:
            print(f"[DEBUG] Wiersz {i}: name='{name}', qty='{qty}', has_numbers={has_numbers}")

        # PRZYPADEK 1: Kontynuacja nazwy (nazwa bez liczb)
        if name and not has_numbers and current_item: 
            current_item["name"] = ((current_item.get("name") or "") + " " + (name or "")).strip()
            if debug:
                print(f"[DEBUG]   -> Kontynuacja nazwy: '{current_item['name']}'")
            continue
        
        # PRZYPADEK 1b: Wiersz z liczbami bez nazwy - traktuj jako uzupełnienie poprzedniej pozycji
        if (not name) and has_numbers and current_item:
            # uzupełnij tylko te pola, które są dostępne
            current_item["qty"] = current_item.get("qty") or (qty or None)
            current_item["unit"] = current_item.get("unit") or (unit or None)
            if price:
                current_item["price_net"] = norm_num(price)
            current_item["vat"] = current_item.get("vat") or (vat or None)
            if net:
                current_item["net"] = norm_num(net)
            if gross:
                current_item["gross"] = norm_num(gross)

            if debug:
                print(f"[DEBUG]   -> Uzupełnienie liczb dla poprzedniej pozycji: {current_item}")
            continue

        # PRZYPADEK 2: Nowa pozycja (nazwa lub liczby)
        if name or has_numbers:
            item = {
                "name": (name or "").strip(),
                "qty": qty or None,
                "unit": unit or None,
                "price_net": norm_num(price) if price else None,
                "vat": vat or None,
                "net": norm_num(net) if net else None,
                "gross": norm_num(gross) if gross else None,
            }
            items.append(item)
            current_item = item
            
            if debug:
                print(f"[DEBUG] -> Nowa pozycja: {item}")
            
            if debug: 
                debug_rows_data.append({
                    "row_idx": i,
                    "cells": {k: [w["text"] for w in v] for k, v in cells.items()},
                    "item": item
                })

    # 5. Zwróć wyniki
    debug_info = {
        "rows_count": len(rows),
        "header_idx": header_idx,
        "columns": columns,
        "items_count": len(items)
    }
    
    if debug:
        debug_info["rows"] = rows
        debug_info["debug_rows_data"] = debug_rows_data

    return items, debug_info