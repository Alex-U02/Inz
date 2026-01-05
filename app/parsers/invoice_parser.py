from typing import Dict, Any
from app.parsers.table_parser import parse_table_fields
from app.parsers.text_parser import parse_text_fields


def parse_invoice(raw_text: str, words, debug: bool = False) -> Dict[str, Any]:
    header = parse_text_fields(raw_text or "")

    items, debug_info = parse_table_fields(words, debug=debug)

    result = {**header, "items": items}

    if debug:
        result["debug"] = debug_info

    return result
