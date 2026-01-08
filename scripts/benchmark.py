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

    # OCR invoices — klucz: layout
    cur.execute("SELECT * FROM ocr_invoices")
    ocr_invoices = defaultdict(dict)
    for row in cur.fetchall():
        ocr_invoices[row["engine"]][row["layout"]] = dict(row)

    # OCR items — klucz: layout
    cur.execute("""
        SELECT oi.*, oi2.engine, oi2.layout
        FROM ocr_items oi
        JOIN ocr_invoices oi2
        ON oi.ocr_invoice_id = oi2.id
    """)
    ocr_items = defaultdict(lambda: defaultdict(list))
    for row in cur.fetchall():
        ocr_items[row["engine"]][row["layout"]].append(dict(row))

    # OCR runs
    cur.execute("SELECT * FROM ocr_runs")
    ocr_runs = defaultdict(list)
    for row in cur.fetchall():
        ocr_runs[row["engine"]].append(dict(row))

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
    results = defaultdict(lambda: defaultdict(int))

    for engine, invoices in ocr_invoices.items():
        for layout, ocr in invoices.items():
            gt = gt_invoices.get(layout)
            if not gt:
                continue

            for field in FIELDS:
                gt_val = str(gt.get(field))
                ocr_val = str(ocr.get(field))

                if gt_val == ocr_val:
                    results[engine]["correct"] += 1
                else:
                    results[engine]["wrong"] += 1

                if ocr_val in [None, "None", "", "null"]:
                    results[engine]["missing"] += 1

    return results


# ============================================
# ITEM-LEVEL COMPARISON
# ============================================

def compare_items(gt_items, ocr_items):
    results = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for engine, invoices in ocr_items.items():
        for layout, ocr_list in invoices.items():
            gt_list = gt_items.get(layout, [])

            gt_names = [i["name"] for i in gt_list]
            ocr_names = [i["name"] for i in ocr_list]

            for name in ocr_names:
                if name in gt_names:
                    results[engine]["tp"] += 1
                else:
                    results[engine]["fp"] += 1

            for name in gt_names:
                if name not in ocr_names:
                    results[engine]["fn"] += 1

    return results


# ============================================
# NUMERIC ACCURACY
# ============================================

NUMERIC_FIELDS = ["price_net", "vat", "net", "gross"]

def compare_numeric(gt_items, ocr_items):
    results = defaultdict(lambda: {"mae": [], "mre": []})

    for engine, invoices in ocr_items.items():
        for layout, ocr_list in invoices.items():
            gt_list = gt_items.get(layout, [])

            for gt, ocr in zip(gt_list, ocr_list):
                for field in NUMERIC_FIELDS:
                    gt_val = safe_float(gt.get(field))
                    ocr_val = safe_float(ocr.get(field))

                    if gt_val is None or ocr_val is None:
                        continue

                    results[engine]["mae"].append(abs(gt_val - ocr_val))
                    if gt_val != 0:
                        results[engine]["mre"].append(abs(gt_val - ocr_val) / gt_val)

    return results


# ============================================
# TIME ANALYSIS
# ============================================

def analyze_times(ocr_runs):
    results = {}

    for engine, runs in ocr_runs.items():
        times = [r["duration_ms"] for r in runs]
        if not times:
            continue

        results[engine] = {
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "count": len(times)
        }

    return results


# ============================================
# PER-LAYOUT ANALYSIS
# ============================================

def analyze_per_layout(gt_invoices, gt_items, ocr_invoices, ocr_items):
    layout_stats = defaultdict(lambda: defaultdict(lambda: {
        "fields_correct": 0,
        "fields_total": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "mae": [],
        "mre": []
    }))

    # ============================
    # Pola faktury
    # ============================
    for engine, invoices in ocr_invoices.items():
        for raw_layout, ocr in invoices.items():

            # sprowadzamy layout1_0 → layout1
            layout = raw_layout.split("_")[0]

            gt = gt_invoices.get(raw_layout)
            if not gt:
                continue

            for field in FIELDS:
                gt_val = str(gt.get(field))
                ocr_val = str(ocr.get(field))

                if gt_val == ocr_val:
                    layout_stats[engine][layout]["fields_correct"] += 1

                layout_stats[engine][layout]["fields_total"] += 1

    # ============================
    # Pozycje + liczby
    # ============================
    for engine, invoices in ocr_items.items():
        for raw_layout, ocr_list in invoices.items():
            layout = raw_layout.split("_")[0]
            gt_list = gt_items.get(raw_layout, [])
            gt = gt_invoices.get(raw_layout)
            if not gt:
                continue

            gt_names = [i["name"] for i in gt_list]
            ocr_names = [i["name"] for i in ocr_list]

            for name in ocr_names:
                if name in gt_names:
                    layout_stats[engine][layout]["tp"] += 1
                else:
                    layout_stats[engine][layout]["fp"] += 1

            for name in gt_names:
                if name not in ocr_names:
                    layout_stats[engine][layout]["fn"] += 1

            for gt_item, ocr_item in zip(gt_list, ocr_list):
                for field in NUMERIC_FIELDS:
                    gt_val = safe_float(gt_item.get(field))
                    ocr_val = safe_float(ocr_item.get(field))
                    if gt_val is None or ocr_val is None:
                        continue

                    layout_stats[engine][layout]["mae"].append(abs(gt_val - ocr_val))
                    if gt_val != 0:
                        layout_stats[engine][layout]["mre"].append(abs(gt_val - ocr_val) / gt_val)

    return layout_stats


# ============================================
# REPORT GENERATION
# ============================================

def generate_report(field_stats, item_stats, numeric_stats, time_stats, layout_stats):
    lines = []
    lines.append("=== RAPORT BENCHMARKU OCR ===\n")

    # Dokładność pól faktury
    lines.append("\n--- DOKŁADNOŚĆ PÓL FAKTURY ---")
    for engine, stats in field_stats.items():
        total = stats["correct"] + stats["wrong"]
        acc = stats["correct"] / total if total else 0
        lines.append(f"\n{engine}: dokładność={acc:.3f}, brakujące={stats['missing']}")

    # Dokładność pozycji towarowych
    lines.append("\n--- DOKŁADNOŚĆ POZYCJI TOWAROWYCH ---")
    for engine, stats in item_stats.items():
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        recall = tp / (tp + fn) if tp + fn else 0
        precision = tp / (tp + fp) if tp + fp else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        lines.append(f"\n{engine}: czułość={recall:.3f}, precyzja={precision:.3f}, F1={f1:.3f}")

    # Dokładność wartości liczbowych
    lines.append("\n--- DOKŁADNOŚĆ WARTOŚCI LICZBOWYCH ---")
    for engine, stats in numeric_stats.items():
        mae = sum(stats["mae"]) / len(stats["mae"]) if stats["mae"] else 0
        mre = sum(stats["mre"]) / len(stats["mre"]) if stats["mre"] else 0
        lines.append(f"\n{engine}: MAE={mae:.3f}, MRE={mre:.3f}")

    # Czas działania OCR
    lines.append("\n--- CZAS DZIAŁANIA OCR ---")
    for engine, stats in time_stats.items():
        lines.append(
            f"\n{engine}: średnia={stats['avg']:.1f} ms, "
            f"min={stats['min']} ms, max={stats['max']} ms, próby={stats['count']}"
        )

    # Analiza per layout
    lines.append("\n--- ANALIZA PER LAYOUT ---")
    for engine, layouts in layout_stats.items():
        lines.append(f"\n### Silnik: {engine}")

        for layout, stats in layouts.items():
            fields_acc = stats["fields_correct"] / stats["fields_total"] if stats["fields_total"] else 0

            tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
            recall = tp / (tp + fn) if tp + fn else 0
            precision = tp / (tp + fp) if tp + fp else 0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

            mae = sum(stats["mae"]) / len(stats["mae"]) if stats["mae"] else 0

            lines.append(
                f"\n  Layout {layout}: pola={fields_acc:.3f}, F1={f1:.3f}, MAE={mae:.1f}"
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
        "layouts": layout_stats
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    print(f"Dane zapisane do {JSON_PATH}")


main()
