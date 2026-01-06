import sqlite3

DB_PATH = "invoices.db"  # lub pełna ścieżka jeśli potrzebujesz

def drop_unused_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables_to_drop = ["invoices", "items"]

    for table in tables_to_drop:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"Usunięto tabelę: {table}")
        except Exception as e:
            print(f"Błąd przy usuwaniu {table}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    drop_unused_tables()
