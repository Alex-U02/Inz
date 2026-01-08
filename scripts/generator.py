import random, json, pathlib
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
import pdfkit
from pdf2image import convert_from_path

# ---------------------------------------
# DB – Ground Truth
# ---------------------------------------
from app.db.init_db import init_db
from app.db.crud_ground_truth import save_ground_truth, clear_ground_truth

# ---------------------------------------
# KONFIGURACJA PDF
# ---------------------------------------

path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# ---------------------------------------
# DANE WEJŚCIOWE
# ---------------------------------------

pool = json.load(open("data/contractors.json", encoding="utf-8"))
company_names = pool["company_names"]
addresses = pool["addresses"]

items = json.load(open("data/items.json", encoding="utf-8"))

templates_dir = pathlib.Path("layouts")
out_dir = pathlib.Path("out")
pdf_dir = out_dir / "pdf"
png_dir = out_dir / "png"

pdf_dir.mkdir(parents=True, exist_ok=True)
png_dir.mkdir(parents=True, exist_ok=True)

env = Environment(loader=FileSystemLoader("layouts"))

# ---------------------------------------
# GENEROWANIE KONTRAHENTA
# ---------------------------------------

def generate_contractor():
    return {
        "name": random.choice(company_names),
        "address": random.choice(addresses),
        "nip": "".join(str(random.randint(0,9)) for _ in range(10)),
        "account": "PL" + "".join(str(random.randint(0,9)) for _ in range(26))
    }

# ---------------------------------------
# GENEROWANIE FAKTURY
# ---------------------------------------

def generate_payload(template_name: str):
    seller = generate_contractor()
    buyer = generate_contractor()

    # DATY
    sale_date_dt = datetime.now() - timedelta(days=random.randint(1, 60))
    issue_date_dt = sale_date_dt + timedelta(days=random.randint(0, 3))
    payment_due_dt = issue_date_dt + timedelta(days=random.randint(7, 21))

    sale_date = sale_date_dt.strftime("%Y-%m-%d")
    issue_date = issue_date_dt.strftime("%Y-%m-%d")
    payment_due = payment_due_dt.strftime("%Y-%m-%d")

    payment_methods = ["Przelew", "Gotówka", "Karta", "BLIK", "PayPal"]
    payment_method = random.choice(payment_methods)

    num_items = random.randint(1, min(8, len(items)))
    products = random.sample(items, num_items)

    invoice_items = []
    for product in products:
        qty = random.randint(1, 10)
        net = product["price_net"] * qty
        vat_amount = net * product["vat"] / 100
        gross = net + vat_amount

        invoice_items.append({
            "name": product["name"],
            "unit": product["unit"],
            "qty": qty,
            "price_net": product["price_net"],
            "vat": product["vat"],
            "net": net,
            "gross": gross
        })

    total_net = sum(i["net"] for i in invoice_items)
    total_vat = sum(i["net"] * i["vat"] / 100 for i in invoice_items)
    total_gross = sum(i["gross"] for i in invoice_items)

    return {
        "invoice_number": f"FV/{random.randint(1000,9999)}",
        "issue_date": issue_date,
        "sale_date": sale_date,
        "currency": "PLN",

        "seller_name": seller["name"],
        "seller_address": seller["address"],
        "seller_nip": seller["nip"],
        "seller_account": seller["account"],
        "seller_regon": str(random.randint(100000000, 999999999)),

        "buyer_name": buyer["name"],
        "buyer_address": buyer["address"],
        "buyer_nip": buyer["nip"],

        "items": invoice_items,

        "total_net": total_net,
        "total_vat": total_vat,
        "total_gross": total_gross,

        "payment_due": payment_due,
        "payment_method": payment_method,
        "notes": "Dziękujemy za współpracę",

        "order_number": f"ORD-{random.randint(100,999)}",
    }

# ---------------------------------------
# RENDEROWANIE PDF + PNG
# ---------------------------------------

def render_invoice(template_name, payload, idx):
    tpl = env.get_template(template_name)
    html_str = tpl.render(**payload)

    pdf_path = pdf_dir / f"{pathlib.Path(template_name).stem}_{idx}.pdf"
    pdfkit.from_string(html_str, str(pdf_path), configuration=config)
    print("Wygenerowano PDF:", pdf_path)

    images = convert_from_path(
        str(pdf_path),
        dpi=300,
        poppler_path=r"C:\Program Files\poppler-25.07.0\Library\bin"
    )

    for page_num, img in enumerate(images, start=1):
        png_path = png_dir / f"{pdf_path.stem}.png"
        img.save(png_path, "PNG")
        print("Wygenerowano PNG:", png_path)

# ---------------------------------------
# GŁÓWNA PĘTLA GENEROWANIA
# ---------------------------------------

if __name__ == "__main__":
    init_db()
    clear_ground_truth()

    for template in templates_dir.glob("*.html"):
        base_layout = pathlib.Path(template.name).stem  # layout1
        for i in range(2):
            payload = generate_payload(template.name)
            full_layout = f"{base_layout}_{i}"          # layout1_0
            save_ground_truth(payload, full_layout)
            render_invoice(template.name, payload, i)

