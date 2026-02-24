import sqlite3
from collections import defaultdict
import json

DB_PATH = "invoices.db"
REPORT_PATH = "out/results/benchmark_report.txt"
JSON_PATH = "out/results/benchmark_data.json"

# ============================================
# HELPERS
# ============================================

def safe_float(x):
    try:
        return float(x)
    except:
        return None


def normalize_text(v):
    """Normalizacja do porównań pól tekstowych."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ["none", "null", ""]:
        return None
    # ujednolicenie białych znaków
    s = " ".join(s.split())
    return s


def is_missing(v):
    v = normalize_text(v)
    return v is None


# ============================================
# LOAD DATA
# ============================================

def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Ground truth invoices — klucz: layout
    cur.execute("SELECT * FROM ground_truth_invoices")
    gt_invoices = {row["layout"]: dict(row) for row in cur.fetchall()}

    # Ground truth items — klucz: layout
    cur.execute("""
        SELECT gti.*, gti2.layout
        FROM ground_truth_items gti
        JOIN ground_truth_invoices gti2
        ON gti.invoice_id = gti2.id
    """)
    gt_items = defaultdict(list)
    for row in cur.fetchall():
        gt_items[row["layout"]].append(dict(row))

    # OCR invoices — klucz: engine -> input_type -> layout
    cur.execute("SELECT * FROM ocr_invoices")
    ocr_invoices = defaultdict(lambda: defaultdict(dict))
    for row in cur.fetchall():
        ocr_invoices[row["engine"]][row["input_type"]][row["layout"]] = dict(row)

    # OCR items — klucz: engine -> input_type -> layout
    cur.execute("""
        SELECT oi.*, oi2.engine, oi2.layout, oi2.input_type
        FROM ocr_items oi
        JOIN ocr_invoices oi2
        ON oi.ocr_invoice_id = oi2.id
    """)
    ocr_items = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in cur.fetchall():
        ocr_items[row["engine"]][row["input_type"]][row["layout"]].append(dict(row))

    # OCR runs — klucz: engine -> input_type
    cur.execute("SELECT * FROM ocr_runs")
    ocr_runs = defaultdict(lambda: defaultdict(list))
    for row in cur.fetchall():
        ocr_runs[row["engine"]][row["input_type"]].append(dict(row))

    conn.close()
    return gt_invoices, gt_items, ocr_invoices, ocr_items, ocr_runs


# ============================================
# FIELD-LEVEL COMPARISON
# ============================================

FIELDS = [
    "invoice_number", "issue_date", "sale_date", "payment_due",
    "currency", "seller_name", "seller_address", "seller_nip",
    "seller_account", "seller_regon", "buyer_name", "buyer_address",
    "buyer_nip", "order_number", "payment_method", "notes",
    "total_net", "total_vat", "total_gross"
]

def compare_fields(gt_invoices, ocr_invoices):
    """
    Wynik: results[engine][input_type] = {correct, wrong, missing}
    """
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for engine, by_type in ocr_invoices.items():
        for input_type, invoices in by_type.items():
            for layout, ocr in invoices.items():
                gt = gt_invoices.get(layout)
                if not gt:
                    continue

                for field in FIELDS:
                    gt_val = normalize_text(gt.get(field))
                    ocr_val = normalize_text(ocr.get(field))

                    if gt_val == ocr_val:
                        results[engine][input_type]["correct"] += 1
                    else:
                        results[engine][input_type]["wrong"] += 1

                    if is_missing(ocr.get(field)):
                        results[engine][input_type]["missing"] += 1

    return results


# ============================================
# ITEM-LEVEL COMPARISON
# ============================================

def compare_items(gt_items, ocr_items):
    """
    Wynik: results[engine][input_type] = {tp, fp, fn}
    TP/FP/FN liczone po dopasowaniu nazwy pozycji.
    """
    results = defaultdict(lambda: defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0}))

    for engine, by_type in ocr_items.items():
        for input_type, invoices in by_type.items():
            for layout, ocr_list in invoices.items():
                gt_list = gt_items.get(layout, [])

                gt_names = [normalize_text(i.get("name")) for i in gt_list if normalize_text(i.get("name"))]
                ocr_names = [normalize_text(i.get("name")) for i in ocr_list if normalize_text(i.get("name"))]

                for name in ocr_names:
                    if name in gt_names:
                        results[engine][input_type]["tp"] += 1
                    else:
                        results[engine][input_type]["fp"] += 1

                for name in gt_names:
                    if name not in ocr_names:
                        results[engine][input_type]["fn"] += 1

    return results


# ============================================
# NUMERIC ACCURACY
# ============================================

NUMERIC_FIELDS = ["price_net", "vat", "net", "gross"]

def compare_numeric(gt_items, ocr_items):
    """
    Wynik: results[engine][input_type] = {mae: [...], mre: [...]}
    Uwaga: zip(gt_list, ocr_list) zakłada podobną kolejność w listach.
    """
    results = defaultdict(lambda: defaultdict(lambda: {"mae": [], "mre": []}))

    for engine, by_type in ocr_items.items():
        for input_type, invoices in by_type.items():
            for layout, ocr_list in invoices.items():
                gt_list = gt_items.get(layout, [])

                for gt, ocr in zip(gt_list, ocr_list):
                    for field in NUMERIC_FIELDS:
                        gt_val = safe_float(gt.get(field))
                        ocr_val = safe_float(ocr.get(field))

                        if gt_val is None or ocr_val is None:
                            continue

                        results[engine][input_type]["mae"].append(abs(gt_val - ocr_val))
                        if gt_val != 0:
                            results[engine][input_type]["mre"].append(abs(gt_val - ocr_val) / gt_val)

    return results


# ============================================
# TIME ANALYSIS
# ============================================

def analyze_times(ocr_runs):
    """
    Wynik: results[engine][input_type] = {avg, min, max, count}
    """
    results = defaultdict(dict)

    for engine, by_type in ocr_runs.items():
        results[engine] = {}
        for input_type, runs in by_type.items():
            times = [r["duration_ms"] for r in runs if r.get("duration_ms") is not None]
            if not times:
                continue

            results[engine][input_type] = {
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "count": len(times),
            }

    return results


# ============================================
# PER-LAYOUT ANALYSIS
# ============================================

def analyze_per_layout(gt_invoices, gt_items, ocr_invoices, ocr_items):
    """
    Wynik: layout_stats[engine][input_type][base_layout] = stats
    base_layout to np. "layout1" (bez _0,_1...).
    """
    layout_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "fields_correct": 0,
        "fields_total": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "mae": [],
        "mre": []
    })))

    # ============================
    # Pola faktury
    # ============================
    for engine, by_type in ocr_invoices.items():
        for input_type, invoices in by_type.items():
            for raw_layout, ocr in invoices.items():
                base_layout = raw_layout.split("_")[0]
                gt = gt_invoices.get(raw_layout)
                if not gt:
                    continue

                for field in FIELDS:
                    gt_val = normalize_text(gt.get(field))
                    ocr_val = normalize_text(ocr.get(field))

                    if gt_val == ocr_val:
                        layout_stats[engine][input_type][base_layout]["fields_correct"] += 1

                    layout_stats[engine][input_type][base_layout]["fields_total"] += 1

    # ============================
    # Pozycje + liczby
    # ============================
    for engine, by_type in ocr_items.items():
        for input_type, invoices in by_type.items():
            for raw_layout, ocr_list in invoices.items():
                base_layout = raw_layout.split("_")[0]
                gt_list = gt_items.get(raw_layout, [])
                gt = gt_invoices.get(raw_layout)
                if not gt:
                    continue

                gt_names = [normalize_text(i.get("name")) for i in gt_list if normalize_text(i.get("name"))]
                ocr_names = [normalize_text(i.get("name")) for i in ocr_list if normalize_text(i.get("name"))]

                for name in ocr_names:
                    if name in gt_names:
                        layout_stats[engine][input_type][base_layout]["tp"] += 1
                    else:
                        layout_stats[engine][input_type][base_layout]["fp"] += 1

                for name in gt_names:
                    if name not in ocr_names:
                        layout_stats[engine][input_type][base_layout]["fn"] += 1

                for gt_item, ocr_item in zip(gt_list, ocr_list):
                    for field in NUMERIC_FIELDS:
                        gt_val = safe_float(gt_item.get(field))
                        ocr_val = safe_float(ocr_item.get(field))
                        if gt_val is None or ocr_val is None:
                            continue

                        layout_stats[engine][input_type][base_layout]["mae"].append(abs(gt_val - ocr_val))
                        if gt_val != 0:
                            layout_stats[engine][input_type][base_layout]["mre"].append(abs(gt_val - ocr_val) / gt_val)

    return layout_stats


# ============================================
# REPORT GENERATION
# ============================================

def _calc_field_acc(stats):
    total = stats.get("correct", 0) + stats.get("wrong", 0)
    return stats.get("correct", 0) / total if total else 0


def _calc_prf(stats):
    tp, fp, fn = stats.get("tp", 0), stats.get("fp", 0), stats.get("fn", 0)
    recall = tp / (tp + fn) if (tp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return precision, recall, f1


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0


def generate_report(field_stats, item_stats, numeric_stats, time_stats, layout_stats):
    lines = []
    lines.append("=== RAPORT BENCHMARKU OCR (ENGINE x INPUT_TYPE) ===\n")

    # --------------------------------------------
    # Dokładność pól faktury
    # --------------------------------------------
    lines.append("\n--- DOKŁADNOŚĆ PÓL FAKTURY ---")
    for engine, by_type in field_stats.items():
        for input_type, stats in by_type.items():
            acc = _calc_field_acc(stats)
            lines.append(
                f"\n{engine}/{input_type}: dokładność={acc:.3f}, "
                f"correct={stats.get('correct',0)}, wrong={stats.get('wrong',0)}, missing={stats.get('missing',0)}"
            )

    # --------------------------------------------
    # Dokładność pozycji towarowych
    # --------------------------------------------
    lines.append("\n--- DOKŁADNOŚĆ POZYCJI TOWAROWYCH ---")
    for engine, by_type in item_stats.items():
        for input_type, stats in by_type.items():
            precision, recall, f1 = _calc_prf(stats)
            lines.append(
                f"\n{engine}/{input_type}: precyzja={precision:.3f}, czułość={recall:.3f}, F1={f1:.3f} "
                f"(tp={stats['tp']}, fp={stats['fp']}, fn={stats['fn']})"
            )

    # --------------------------------------------
    # Dokładność wartości liczbowych
    # --------------------------------------------
    lines.append("\n--- DOKŁADNOŚĆ WARTOŚCI LICZBOWYCH ---")
    for engine, by_type in numeric_stats.items():
        for input_type, stats in by_type.items():
            mae = _mean(stats["mae"])
            mre = _mean(stats["mre"])
            lines.append(f"\n{engine}/{input_type}: MAE={mae:.3f}, MRE={mre:.3f} (n={len(stats['mae'])})")

    # --------------------------------------------
    # Czas działania OCR
    # --------------------------------------------
    lines.append("\n--- CZAS DZIAŁANIA OCR ---")
    for engine, by_type in time_stats.items():
        for input_type, stats in by_type.items():
            lines.append(
                f"\n{engine}/{input_type}: średnia={stats['avg']:.1f} ms, "
                f"min={stats['min']} ms, max={stats['max']} ms, próby={stats['count']}"
            )

    # --------------------------------------------
    # Analiza per layout (bazowy: layout1..layout8)
    # --------------------------------------------
    lines.append("\n--- ANALIZA PER LAYOUT (ENGINE x INPUT_TYPE) ---")
    for engine, by_type in layout_stats.items():
        for input_type, layouts in by_type.items():
            lines.append(f"\n### Silnik: {engine} / Typ: {input_type}")

            for layout, stats in layouts.items():
                fields_acc = stats["fields_correct"] / stats["fields_total"] if stats["fields_total"] else 0
                precision, recall, f1 = _calc_prf(stats)
                mae = _mean(stats["mae"])

                lines.append(
                    f"\n  Layout {layout}: pola={fields_acc:.3f}, F1={f1:.3f}, MAE={mae:.1f} "
                    f"(fields_total={stats['fields_total']})"
                )

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Raport zapisany do {REPORT_PATH}")


# ============================================
# MAIN
# ============================================

def main():
    gt_invoices, gt_items, ocr_invoices, ocr_items, ocr_runs = load_data()

    layout_stats = analyze_per_layout(gt_invoices, gt_items, ocr_invoices, ocr_items)
    field_stats = compare_fields(gt_invoices, ocr_invoices)
    item_stats = compare_items(gt_items, ocr_items)
    numeric_stats = compare_numeric(gt_items, ocr_items)
    time_stats = analyze_times(ocr_runs)

    generate_report(field_stats, item_stats, numeric_stats, time_stats, layout_stats)

    json_data = {
        "fields": field_stats,
        "items": item_stats,
        "numeric": numeric_stats,
        "times": time_stats,
        "layouts": layout_stats,
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"Dane zapisane do {JSON_PATH}")


main()