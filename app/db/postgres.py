# app/db/postgres.py

import os
from typing import Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import Config, log_event


def get_db_connection():
    """
    Create and return a PostgreSQL connection using settings from Config.
    """
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        cursor_factory=RealDictCursor,
        sslmode="disable",  # inside Codespaces / local container, SSL not needed
    )
    return conn


def initialize_database():
    """
    Create and seed the products/customers/sales schema in PostgreSQL.
    This is the PostgreSQL equivalent of your current SQLite database.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Drop tables if they already exist (development only).
    # In a real production setup, you would use migrations instead.
    cur.execute("DROP TABLE IF EXISTS sales;")
    cur.execute("DROP TABLE IF EXISTS products;")
    cur.execute("DROP TABLE IF EXISTS customers;")

    # Create products table.
    cur.execute(
        """
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price NUMERIC NOT NULL
        );
        """
    )

    # Create customers table.
    cur.execute(
        """
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL
        );
        """
    )

    # Create sales table with foreign keys.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            sale_date DATE NOT NULL,
            product_id INTEGER NOT NULL REFERENCES products(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            quantity INTEGER NOT NULL,
            total_amount NUMERIC NOT NULL
        );
        """
    )

    # Seed data similar to your SQLite version.
    products = [
        ("Laptop Pro 15", "Electronics", 1500),
        ("Laptop Air 13", "Electronics", 1100),
        ("Wireless Mouse", "Accessories", 300),
        ("Office Chair", "Furniture", 800),
        ("USB-C Hub", "Accessories", 250),
    ]

    customers = [
        ("Alice Johnson", "London"),
        ("Bob Smith", "Manchester"),
        ("Charlie Brown", "Birmingham"),
        ("Diana Prince", "Leeds"),
    ]

    sales = [
        ("2025-04-02", 1, 1, 3, 4500),
        ("2025-04-10", 2, 2, 5, 5500),
        ("2025-04-15", 3, 3, 7, 2100),
        ("2025-05-03", 1, 2, 1, 1500),
        ("2025-05-17", 4, 1, 2, 1600),
        ("2025-06-01", 2, 3, 2, 2200),
        ("2025-04-22", 5, 4, 4, 1000),
        ("2025-06-12", 4, 2, 1, 800),
    ]

    cur.executemany(
        "INSERT INTO products (name, category, price) VALUES (%s, %s, %s);",
        products,
    )
    cur.executemany(
        "INSERT INTO customers (name, city) VALUES (%s, %s);",
        customers,
    )
    cur.executemany(
        """
        INSERT INTO sales (sale_date, product_id, customer_id, quantity, total_amount)
        VALUES (%s, %s, %s, %s, %s);
        """,
        sales,
    )

    conn.commit()
    cur.close()
    conn.close()

    log_event(
        "postgres_db_initialized",
        {
            "host": Config.DB_HOST,
            "port": Config.DB_PORT,
            "dbname": Config.DB_NAME,
        },
    )