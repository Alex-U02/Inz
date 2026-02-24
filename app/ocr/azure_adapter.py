import requests
import time
import os

AZURE_ENDPOINT = "https://benchmark-dev-seu-di-alex.cognitiveservices.azure.com/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31"
AZURE_KEY = "BVyBvuQd6mPMxcyG4nMMgzXcMEUBFRGowO5D4UE44cqeaJAmpgMUJQQJ99CAACfhMk5XJ3w3AAALACOGWh7K"


_last_call = 0
MIN_INTERVAL = 3.4


def _respect_rate_limit():
    global _last_call
    now = time.time()
    elapsed = now - _last_call

    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    _last_call = time.time()


def _safe_post(url, headers, data):
    """POST z retry na 429."""
    while True:
        response = requests.post(url, headers=headers, data=data, timeout=30)

        if response.status_code == 429:
            print("[Azure] Limit 20/min — retry za 5s")
            time.sleep(5)
            continue

        return response


def run_azure_ocr(image_bytes: bytes):
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream"
    }

    try:
        _respect_rate_limit()

        print("[Azure] Start analizy...")

        response = _safe_post(AZURE_ENDPOINT, headers, image_bytes)

        if response.status_code != 202:
            print(f"[Azure] Błąd: {response.status_code}")
            try:
                print("[Azure] Body:", response.text)
            except Exception:
                print("[Azure] Body: <nie udało się odczytać response.text>")
            return create_empty_invoice()

        operation_location = response.headers.get("Operation-Location")
        if not operation_location:
            print("[Azure] Brak Operation-Location")
            return create_empty_invoice()

        # Polling
        for _ in range(60):
            time.sleep(2)

            result = requests.get(
                operation_location,
                headers={"Ocp-Apim-Subscription-Key": AZURE_KEY},
                timeout=10
            )

            if result.status_code == 429:
                print("[Azure] Polling throttled — retry za 3s")
                time.sleep(3)
                continue

            result.raise_for_status()
            data = result.json()
            status = data.get("status")

            if status == "succeeded":
                print("[Azure] Analiza zakończona")
                return parse_azure_invoice(data)

            if status == "failed":
                print("[Azure] Azure zwrócił status FAILED")
                return create_empty_invoice()

        print("[Azure] Timeout po 120s")
        return create_empty_invoice()

    except Exception as e:
        print(f"[Azure] Błąd krytyczny: {e}")
        return create_empty_invoice()


def parse_azure_invoice(data: dict):
    """Minimalne parsowanie — tylko wartości zwrócone przez Azure."""
    try:
        analyze_result = data.get("analyzeResult", {})
        documents = analyze_result.get("documents", [])

        if not documents:
            return create_empty_invoice()

        fields = documents[0].get("fields", {})

        def val(f):
            if not f:
                return None
            return (
                f.get("valueString")
                or f.get("valueNumber")
                or f.get("valueDate")
                or f.get("content")
            )

        invoice = {
            "invoice_number": val(fields.get("InvoiceId")),
            "issue_date": val(fields.get("InvoiceDate")),
            "sale_date": None,
            "payment_due": val(fields.get("DueDate")),
            "currency": val(fields.get("CurrencyCode")),

            "seller_name": val(fields.get("VendorName")),
            "seller_address": val(fields.get("VendorAddress")),
            "seller_nip": val(fields.get("VendorTaxId")),
            "seller_account": val(fields.get("VendorAccountNumber")),
            "seller_regon": None,

            "buyer_name": val(fields.get("CustomerName")),
            "buyer_address": val(fields.get("CustomerAddress")),
            "buyer_nip": val(fields.get("CustomerTaxId")),

            "order_number": val(fields.get("PurchaseOrder")),
            "payment_method": None,
            "notes": None,

            "total_net": val(fields.get("SubTotal")),
            "total_vat": val(fields.get("TotalTax")),
            "total_gross": val(fields.get("InvoiceTotal")),
        }

        # Pozycje
        items = []
        arr = fields.get("Items", {}).get("valueArray", [])

        for item in arr:
            obj = item.get("valueObject", {})
            items.append({
                "name": val(obj.get("Description")),
                "qty": val(obj.get("Quantity")),
                "unit": val(obj.get("Unit")),
                "price_net": val(obj.get("UnitPrice")),
                "vat": val(obj.get("TaxRate")),
                "net": val(obj.get("Amount")),
                "gross": val(obj.get("AmountWithTax")),
            })

        invoice["items"] = items
        return invoice

    except:
        return create_empty_invoice()


def create_empty_invoice():
    return {
        "invoice_number": None,
        "issue_date": None,
        "sale_date": None,
        "payment_due": None,
        "currency": None,
        "seller_name": None,
        "seller_address": None,
        "seller_nip": None,
        "seller_account": None,
        "seller_regon": None,
        "buyer_name": None,
        "buyer_address": None,
        "buyer_nip": None,
        "order_number": None,
        "payment_method": None,
        "notes": None,
        "total_net": None,
        "total_vat": None,
        "total_gross": None,
        "items": []
    }
