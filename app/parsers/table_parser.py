import re
from typing import List, Dict, Optional
from collections import defaultdict

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

SUMMARY_WORDS = {
    "suma", "netto", "vat", "brutto", "razem",
    "uwagi", "forma zapłaty", "sposób zapłaty"
}

def is_number(t: str) -> bool:
    return bool(NUMBER.fullmatch(t.replace(",", ".")))

def norm_num(t: Optional[str]) -> Optional[str]:
    if t is None:
        return None
    return t.replace(",", ".").strip()

def is_summary_text(t: str) -> bool:
    tl = t.lower()
    return any(w in tl for w in SUMMARY_WORDS)


# ============================================================
# BLOKOWE WIERSZE
# ============================================================

def group_rows(words: List[Dict], row_tolerance: float = 14.0) -> List[List[Dict]]:
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: (w.get("y", 0.0), w.get("x", 0.0)))

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

    for r in rows:
        r.sort(key=lambda ww: ww["x"])

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
    "nazwa", "pozycja", "opis", "towaru", "usługi", "uslugi"
}

def detect_header_candidates(rows):
    out = []
    for i, row in enumerate(rows):
        text = " ".join(w["text"].lower() for w in row)
        score = sum(1 for kw in HEADER_KEYWORDS if kw in text)
        if score >= 2:
            out.append(i)
    return out

def count_numeric_rows_below(rows, start_idx, max_lookahead=6):
    count = 0
    end = min(len(rows), start_idx + 1 + max_lookahead)
    for i in range(start_idx + 1, end):
        text = " ".join(w["text"] for w in rows[i])
        if any(is_number(tok) for tok in text.replace(",", ".").split()):
            count += 1
    return count

def detect_header_row(rows):
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
        score = width + numeric_below * 1000

        if best_score is None or score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


# ============================================================
# KOLUMNY
# ============================================================

def classify_header_text(txt: str) -> Optional[str]:
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
    if "vat" in t:
        return "vat"
    if "netto" in t:
        return "net"
    if "brutto" in t:
        return "gross"

    return None


def build_column_model(header_row):
    headers = []
    for w in header_row:
        col_type = classify_header_text(w["text"])
        if col_type:
            x_center = w["x"] + w["w"] / 2
            headers.append((x_center, col_type))

    headers.sort(key=lambda h: h[0])

    columns = []
    for i, (xc, col_type) in enumerate(headers):
        if i == 0:
            left = xc - 350
        else:
            left = (headers[i - 1][0] + xc) / 2

        if i == len(headers) - 1:
            right = xc + 350
        else:
            right = (xc + headers[i + 1][0]) / 2

        columns.append({"type": col_type, "x_min": left, "x_max": right})

    return columns


def assign_cells_to_columns(row, columns):
    out = defaultdict(list)
    for w in row:
        xc = w["x"] + w["w"] / 2
        for col in columns:
            if col["x_min"] <= xc <= col["x_max"]:
                out[col["type"]].append(w)
                break
    return out


def join_text(cells):
    return " ".join(w["text"] for w in sorted(cells, key=lambda ww: ww["x"])).strip()


# ============================================================
# GŁÓWNY PARSER TABELI
# ============================================================

def parse_table_fields(words: List[Dict], debug=False):
    rows = group_rows(words, row_tolerance=12)

    header_idx = detect_header_row(rows)
    if header_idx is None:
        return [], {"error": "header_not_found", "rows": rows}

    header_row = rows[header_idx]
    columns = build_column_model(header_row)

    items = []
    current = None
    debug_rows = []

    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        row_text = " ".join(w["text"] for w in row)

        if is_summary_text(row_text):
            break

        cells = assign_cells_to_columns(row, columns)

        name = join_text(cells.get("name", []))
        qty = join_text(cells.get("qty", []))
        unit = join_text(cells.get("unit", []))
        price = join_text(cells.get("price_net", []))
        vat = join_text(cells.get("vat", []))
        net = join_text(cells.get("net", []))
        gross = join_text(cells.get("gross", []))

        # ----------------------------------------------------
        # HEURYSTYKA: jeśli unit zawiera liczbę → liczba to qty
        # ----------------------------------------------------
        if unit and any(ch.isdigit() for ch in unit) and not qty:
            parts = unit.split()
            nums = [p for p in parts if p.replace(",", ".").replace(".", "").isdigit()]
            if nums:
                qty = nums[0]
                unit = " ".join(p for p in parts if p not in nums)

        # ----------------------------------------------------
        # HEURYSTYKA: jeśli net = price * qty → wylicz qty
        # ----------------------------------------------------
        if not qty and price and net:
            try:
                p = float(price.replace(",", "."))
                n = float(net.replace(",", "."))
                if p > 0 and n % p == 0:
                    qty = str(int(n / p))
            except:
                pass

        # ----------------------------------------------------
        # KONTYNUACJA NAZWY
        # ----------------------------------------------------
        has_number = any(is_number(x) for x in [qty, price, net, gross] if x)

        if name and not has_number and current:
            current["name"] = (current["name"] + " " + name).strip()
            continue

        # ----------------------------------------------------
        # NOWA POZYCJA
        # ----------------------------------------------------
        if name or has_number:
            item = {
                "name": name or None,
                "qty": qty or None,
                "unit": unit or None,
                "price_net": norm_num(price) if price else None,
                "vat": vat or None,
                "net": norm_num(net) if net else None,
                "gross": norm_num(gross) if gross else None,
            }
            items.append(item)
            current = item
            continue

    return items, {
        "rows": rows,
        "header_idx": header_idx,
        "columns": columns,
        "assigned_rows": debug_rows,
    }
