"""Seed the demo SQLite database with realistic business data.

Creates tables for: customers, products, orders, order_items, invoices, employees, departments.
Generates realistic data spanning 2 years with seasonal patterns.
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sample_db" / "business.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    budget REAL NOT NULL,
    head_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    salary REAL NOT NULL,
    hire_date TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    industry TEXT NOT NULL,
    region TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('Enterprise', 'Mid-Market', 'SMB')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price REAL NOT NULL,
    cost REAL NOT NULL,
    stock_quantity INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Pending', 'Confirmed', 'Shipped', 'Delivered', 'Cancelled')),
    total_amount REAL NOT NULL,
    discount_percent REAL DEFAULT 0,
    sales_rep_id INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (sales_rep_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    invoice_number TEXT NOT NULL UNIQUE,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled')),
    paid_date TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
"""

# Realistic data generators
COMPANY_NAMES = [
    "Acme Corp", "TechFlow Inc", "GlobalSync Ltd", "NovaStar Systems",
    "Pinnacle Solutions", "CloudBridge IO", "DataVault Corp", "SwiftLogic",
    "CyberNest Inc", "BlueHorizon Tech", "Quantum Dynamics", "PeakForce Ltd",
    "IronClad Security", "NetPulse Systems", "SkyLane Analytics",
    "OmniWare Solutions", "FusionGrid Corp", "ClearPath Digital",
    "EdgePoint Labs", "CoreStack Inc", "MindBridge AI", "AeroSync Ltd",
    "TrueNorth Data", "VeloCity Tech", "PrismView Corp", "HexaCore Systems",
    "TidalWave IO", "NorthStar Consulting", "RapidScale Inc", "InfiniteLoop Tech",
]

INDUSTRIES = ["Technology", "Healthcare", "Finance", "Manufacturing", "Retail", "Education", "Energy"]
REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East"]
TIERS = ["Enterprise", "Mid-Market", "SMB"]

PRODUCT_CATALOG = [
    ("DataPilot Pro", "Software", 299.99, 45.0),
    ("DataPilot Enterprise", "Software", 999.99, 150.0),
    ("Analytics Dashboard", "Software", 149.99, 22.0),
    ("Cloud Storage 1TB", "Infrastructure", 49.99, 12.0),
    ("Cloud Storage 10TB", "Infrastructure", 199.99, 48.0),
    ("API Gateway", "Infrastructure", 79.99, 15.0),
    ("Security Suite", "Security", 399.99, 60.0),
    ("Compliance Module", "Security", 249.99, 37.0),
    ("Training Package", "Services", 599.99, 200.0),
    ("Premium Support", "Services", 199.99, 80.0),
    ("Data Migration", "Services", 1499.99, 500.0),
    ("Custom Integration", "Services", 2499.99, 800.0),
]

DEPARTMENTS = [
    ("Engineering", 2500000, 45),
    ("Sales", 1800000, 30),
    ("Marketing", 900000, 15),
    ("Customer Success", 600000, 12),
    ("Finance", 400000, 8),
    ("HR", 300000, 6),
]

FIRST_NAMES = ["James", "Sarah", "Michael", "Emily", "David", "Lisa", "Robert", "Jennifer",
               "William", "Maria", "Richard", "Linda", "Joseph", "Patricia", "Thomas",
               "Elizabeth", "Daniel", "Susan", "Matthew", "Jessica"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
              "Martin", "Lee", "Thompson", "White", "Harris"]
TITLES = ["Software Engineer", "Senior Engineer", "Sales Representative", "Account Executive",
          "Marketing Manager", "Data Analyst", "Product Manager", "VP of Engineering",
          "Director of Sales", "Support Engineer"]


def seed_database() -> None:
    os.makedirs(DB_PATH.parent, exist_ok=True)

    # Remove existing DB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tables
    cursor.executescript(SCHEMA)

    random.seed(42)  # Reproducible data

    # 1. Departments
    for i, (name, budget, hc) in enumerate(DEPARTMENTS, 1):
        cursor.execute(
            "INSERT INTO departments VALUES (?, ?, ?, ?)",
            (i, name, budget, hc),
        )

    # 2. Employees
    emp_id = 1
    for dept_id in range(1, len(DEPARTMENTS) + 1):
        dept_hc = DEPARTMENTS[dept_id - 1][2]
        for _ in range(min(dept_hc, 8)):  # Cap per dept for demo
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            hire_date = (datetime(2022, 1, 1) + timedelta(days=random.randint(0, 700))).strftime("%Y-%m-%d")
            salary = random.randint(65000, 180000)
            title = random.choice(TITLES)
            cursor.execute(
                "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (emp_id, first, last, f"{first.lower()}.{last.lower()}{emp_id}@datapilot.io",
                 dept_id, title, salary, hire_date),
            )
            emp_id += 1

    total_employees = emp_id - 1
    sales_reps = list(range(1, total_employees + 1))

    # 3. Customers
    for i, company in enumerate(COMPANY_NAMES, 1):
        contact_first = random.choice(FIRST_NAMES)
        contact_last = random.choice(LAST_NAMES)
        created = (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 500))).strftime("%Y-%m-%d")
        cursor.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, company, f"{contact_first} {contact_last}",
             f"{contact_first.lower()}@{company.lower().replace(' ', '')}.com",
             f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
             random.choice(INDUSTRIES), random.choice(REGIONS),
             random.choice(TIERS), created),
        )

    # 4. Products
    for i, (name, cat, price, cost) in enumerate(PRODUCT_CATALOG, 1):
        cursor.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)",
            (i, name, cat, price, cost, random.randint(50, 500), 1),
        )

    # 5. Orders (spanning 2024-2025 with seasonal patterns)
    order_id = 1
    item_id = 1
    base_date = datetime(2024, 1, 1)

    for day_offset in range(550):  # ~1.5 years
        date = base_date + timedelta(days=day_offset)

        # Seasonal multiplier: more orders in Q4, fewer in Q1
        month = date.month
        if month in (10, 11, 12):
            daily_orders = random.randint(3, 8)
        elif month in (1, 2, 3):
            daily_orders = random.randint(1, 4)
        else:
            daily_orders = random.randint(2, 6)

        for _ in range(daily_orders):
            customer_id = random.randint(1, len(COMPANY_NAMES))
            sales_rep = random.choice(sales_reps)
            discount = random.choice([0, 0, 0, 5, 10, 15, 20])

            # Generate order items
            num_items = random.randint(1, 4)
            items = []
            total = 0
            for _ in range(num_items):
                product_id = random.randint(1, len(PRODUCT_CATALOG))
                qty = random.randint(1, 10)
                price = PRODUCT_CATALOG[product_id - 1][2]
                items.append((item_id, order_id, product_id, qty, price))
                total += qty * price
                item_id += 1

            total *= (1 - discount / 100)

            # Determine status based on date
            days_ago = (datetime(2025, 7, 1) - date).days
            if days_ago > 30:
                status = random.choice(["Delivered", "Delivered", "Delivered", "Cancelled"])
            elif days_ago > 7:
                status = random.choice(["Delivered", "Shipped", "Shipped"])
            else:
                status = random.choice(["Pending", "Confirmed", "Shipped"])

            cursor.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, customer_id, date.strftime("%Y-%m-%d"),
                 status, round(total, 2), discount, sales_rep),
            )

            for item in items:
                cursor.execute(
                    "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", item
                )

            order_id += 1

    # 6. Invoices
    invoice_id = 1
    cursor.execute("SELECT id, order_date, total_amount, status FROM orders WHERE status != 'Cancelled'")
    orders = cursor.fetchall()

    for oid, order_date, amount, status in orders:
        issue_date = datetime.strptime(order_date, "%Y-%m-%d")
        due_date = issue_date + timedelta(days=30)
        inv_number = f"INV-{issue_date.strftime('%Y%m')}-{invoice_id:05d}"

        if status == "Delivered":
            inv_status = random.choice(["Paid", "Paid", "Paid", "Overdue"])
            paid_date = (issue_date + timedelta(days=random.randint(5, 45))).strftime("%Y-%m-%d")
            if inv_status == "Overdue":
                paid_date = None
        elif status in ("Shipped", "Confirmed"):
            inv_status = "Sent"
            paid_date = None
        else:
            inv_status = "Draft"
            paid_date = None

        cursor.execute(
            "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (invoice_id, oid, inv_number, order_date,
             due_date.strftime("%Y-%m-%d"), round(amount, 2),
             inv_status, paid_date),
        )
        invoice_id += 1

    conn.commit()

    # Print summary
    for table in ["departments", "employees", "customers", "products", "orders", "order_items", "invoices"]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\nDatabase created at: {DB_PATH}")


if __name__ == "__main__":
    print("Seeding DataPilot demo database...")
    seed_database()
    print("Done!")
