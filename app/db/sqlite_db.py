import sqlite3
from app.config import DB_PATH

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS sales")
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute("DROP TABLE IF EXISTS customers")

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            sale_date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    products = [
        (1, "Laptop Pro 15", "Electronics", 1500),
        (2, "Laptop Air 13", "Electronics", 1100),
        (3, "Wireless Mouse", "Accessories", 300),
        (4, "Office Chair", "Furniture", 800),
        (5, "USB-C Hub", "Accessories", 250),
    ]

    customers = [
        (1, "Alice Johnson", "London"),
        (2, "Bob Smith", "Manchester"),
        (3, "Charlie Brown", "Birmingham"),
        (4, "Diana Prince", "Leeds"),
    ]

    sales = [
        (1, "2025-04-02", 1, 1, 3, 4500),
        (2, "2025-04-10", 2, 2, 5, 5500),
        (3, "2025-04-15", 3, 3, 7, 2100),
        (4, "2025-05-03", 1, 2, 1, 1500),
        (5, "2025-05-17", 4, 1, 2, 1600),
        (6, "2025-06-01", 2, 3, 2, 2200),
        (7, "2025-04-22", 5, 4, 4, 1000),
        (8, "2025-06-12", 4, 2, 1, 800),
    ]

    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?)", customers)
    cur.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", sales)

    conn.commit()
    conn.close()