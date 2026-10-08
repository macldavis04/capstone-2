# create_db.py
# One-time script: builds data/database.sqlite for the Unit 2 capstone.
# Run from the project root. Keep this file OUTSIDE the project folder.
import calendar
import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(42)  # same data every run

DB_PATH = "data/database.sqlite"
os.makedirs("data", exist_ok=True)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.executescript("""
CREATE TABLE sales (
    id INTEGER PRIMARY KEY,
    region TEXT,
    product TEXT,
    revenue REAL,
    date TEXT,          -- 'YYYY-MM-DD'
    units_sold INTEGER
);
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    industry TEXT,
    churn_date TEXT,    -- NULL = active customer
    satisfaction_score REAL  -- 1 to 10
);
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    department TEXT,
    satisfaction_score REAL, -- 1 to 10
    tenure_years REAL
);
""")

# ---------- sales: all of 2025, growth trend, regional differences in Q4 ----------
PRODUCTS = {
    "Analytics Platform": 1200,
    "Data Connector": 350,
    "Support Plan": 180,
    "Training Package": 600,
}
REGION_BASE = {"North": 1.15, "South": 0.90, "East": 1.05, "West": 0.95}
REGION_Q4 = {"North": 1.25, "South": 1.10, "East": 1.30, "West": 0.85}  # West slips in Q4

sales = []
for month in range(1, 13):
    days_in_month = calendar.monthrange(2025, month)[1]
    growth = 1 + 0.03 * (month - 1)
    for region, base in REGION_BASE.items():
        q4 = REGION_Q4[region] if month >= 10 else 1.0
        for product, price in PRODUCTS.items():
            for _ in range(random.randint(4, 8)):
                units = max(1, round(random.randint(2, 10) * base * growth * q4))
                revenue = round(units * price * random.uniform(0.9, 1.1), 2)
                day = random.randint(1, days_in_month)
                sales.append((region, product, revenue, f"2025-{month:02d}-{day:02d}", units))

c.executemany(
    "INSERT INTO sales (region, product, revenue, date, units_sold) VALUES (?, ?, ?, ?, ?)",
    sales,
)

# ---------- customers: ~18% churned during 2025, churned customers less satisfied ----------
PREFIXES = ["Apex", "Summit", "Harbor", "Blue Ridge", "Granite", "Northwind", "Pioneer",
            "Keystone", "Riverbend", "Ironwood", "Crescent", "Lakeshore", "Redwood", "Meridian"]
SUFFIXES = ["Logistics", "Health", "Manufacturing", "Retail", "Financial", "Energy",
            "Foods", "Systems", "Partners", "Labs"]
INDUSTRIES = ["Healthcare", "Manufacturing", "Retail", "Financial Services", "Energy", "Technology"]

used_names = set()
customers = []
while len(customers) < 200:
    name = f"{random.choice(PREFIXES)} {random.choice(SUFFIXES)}"
    if name in used_names:
        name = f"{name} {len(customers) + 1}"
    used_names.add(name)
    churned = random.random() < 0.18
    if churned:
        churn_date = (date(2025, 1, 1) + timedelta(days=random.randint(0, 364))).isoformat()
        score = round(random.uniform(3.0, 6.5), 1)
    else:
        churn_date = None
        score = round(random.uniform(6.0, 9.5), 1)
    customers.append((name, random.choice(INDUSTRIES), churn_date, score))

c.executemany(
    "INSERT INTO customers (name, industry, churn_date, satisfaction_score) VALUES (?, ?, ?, ?)",
    customers,
)

# ---------- employees: department-level satisfaction differences ----------
DEPT_MEAN = {"Engineering": 7.4, "Sales": 6.2, "Support": 5.8,
             "Marketing": 7.0, "Finance": 6.9, "HR": 7.3}
employees = []
for _ in range(120):
    dept = random.choice(list(DEPT_MEAN))
    score = round(min(10, max(1, random.gauss(DEPT_MEAN[dept], 1.0))), 1)
    tenure = round(random.uniform(0.3, 12), 1)
    employees.append((dept, score, tenure))

c.executemany(
    "INSERT INTO employees (department, satisfaction_score, tenure_years) VALUES (?, ?, ?)",
    employees,
)

conn.commit()

# ---------- summary, so you can sanity-check the agent's answers later ----------
print("Rows:", {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("sales", "customers", "employees")})
churned, total = c.execute(
    "SELECT SUM(churn_date IS NOT NULL), COUNT(*) FROM customers").fetchone()
print(f"Churn rate: {churned}/{total} = {churned / total:.1%}")
print("Q4 revenue by region:")
for region, rev in c.execute("""
    SELECT region, ROUND(SUM(revenue), 2) FROM sales
    WHERE CAST(strftime('%m', date) AS INTEGER) BETWEEN 10 AND 12
    GROUP BY region ORDER BY 2 DESC"""):
    print(f"  {region}: ${rev:,.2f}")
avg = c.execute("SELECT ROUND(AVG(satisfaction_score), 2) FROM employees").fetchone()[0]
print(f"Average employee satisfaction: {avg} / 10")

conn.close()
print(f"\nCreated {DB_PATH}")