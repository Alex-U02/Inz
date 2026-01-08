import requests

# Wstaw swoje dane z Azure Foundry
AZURE_ENDPOINT = "https://<region>.api.cognitive.microsoft.com/documentintelligence/documentModels/prebuilt-invoice:analyze?api-version=2024-02-29-preview"
AZURE_KEY = "<YOUR_KEY>"


def run_azure_ocr(image_bytes: bytes):
    """
    Wysyła obraz do Azure Document Intelligence i zwraca znormalizowany wynik.
    """
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream"
    }

    response = requests.post(
        AZURE_ENDPOINT,
        headers=headers,
        data=image_bytes
    )

    response.raise_for_status()
    data = response.json()

    return parse_azure_invoice(data)


def parse_azure_invoice(data: dict):
    """
    Normalizuje JSON z Azure Document Intelligence do formatu używanego w Twoim systemie.
    """
    doc = data.get("documents", [{}])[0]
    fields = doc.get("fields", {})

    def get(field_name):
        field = fields.get(field_name)
        if not field:
            return None
        return field.get("valueString") or field.get("content") or field.get("valueNumber")

    parsed = {
        "invoice_number": get("InvoiceId"),
        "issue_date": get("InvoiceDate"),
        "sale_date": get("PurchaseOrderDate") or get("InvoiceDate"),
        "payment_due": get("DueDate"),
        "currency": get("CurrencyCode"),

        "seller_name": get("VendorName"),
        "seller_address": get("VendorAddress"),
        "seller_nip": get("VendorTaxId"),
        "seller_account": get("VendorBankAccountNumber"),
        "seller_regon": None,

        "buyer_name": get("CustomerName"),
        "buyer_address": get("CustomerAddress"),
        "buyer_nip": get("CustomerTaxId"),

        "order_number": get("PurchaseOrder"),
        "payment_method": get("PaymentMethod"),
        "notes": get("Notes"),

        "total_net": get("SubTotal"),
        "total_vat": get("TotalTax"),
        "total_gross": get("InvoiceTotal"),

        "items": []
    }

    items = fields.get("Items", {}).get("valueArray", [])

    for item in items:
        f = item.get("valueObject", {})

        def g(name):
            field = f.get(name)
            if not field:
                return None
            return field.get("valueString") or field.get("content") or field.get("valueNumber")

        parsed["items"].append({
            "name": g("Description"),
            "qty": g("Quantity"),
            "unit": g("Unit"),
            "price_net": g("UnitPrice"),
            "vat": g("TaxRate"),
            "net": g("Amount"),
            "gross": g("TotalPrice")
        })

    return parsed
