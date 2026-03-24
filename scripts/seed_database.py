"""Seed the demo SQLite database with realistic B2B SaaS metrics data.

Creates tables for: accounts, subscriptions, mrr_events, feature_usage,
support_tickets, invoices. Generates 18 months of realistic SaaS data
with churn patterns, expansion revenue, and seasonal trends.
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sample_db" / "business.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL CHECK (plan IN ('Free', 'Starter', 'Growth', 'Business', 'Enterprise')),
    mrr REAL NOT NULL DEFAULT 0,
    arr REAL GENERATED ALWAYS AS (mrr * 12) STORED,
    status TEXT NOT NULL CHECK (status IN ('active', 'churned', 'trial', 'paused')),
    industry TEXT NOT NULL,
    employee_count INTEGER NOT NULL,
    signup_date TEXT NOT NULL,
    churn_date TEXT,
    region TEXT NOT NULL,
    csm_owner TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    mrr REAL NOT NULL,
    seats INTEGER NOT NULL DEFAULT 1,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    is_current INTEGER NOT NULL DEFAULT 1,
    billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('monthly', 'annual')),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS mrr_events (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('new', 'expansion', 'contraction', 'churn', 'reactivation')
    ),
    mrr_delta REAL NOT NULL,
    previous_mrr REAL NOT NULL DEFAULT 0,
    new_mrr REAL NOT NULL,
    event_date TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS feature_usage (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    feature_name TEXT NOT NULL,
    daily_active_users INTEGER NOT NULL DEFAULT 0,
    event_count INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    category TEXT NOT NULL CHECK (
        category IN ('bug', 'feature_request', 'billing',
                     'onboarding', 'integration', 'performance')
    ),
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    first_response_minutes INTEGER,
    csat_score INTEGER CHECK (csat_score BETWEEN 1 AND 5),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    invoice_number TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'void')),
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    paid_date TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
"""

# ── Realistic SaaS company data ──────────────────────────────────

COMPANIES = [
    ("Acme Corp", "acme.com", "Manufacturing", 450, "North America"),
    ("TechFlow Solutions", "techflow.io", "Technology", 120, "North America"),
    ("MediCare Plus", "medicareplus.com", "Healthcare", 2200, "North America"),
    ("FinEdge Capital", "finedge.com", "Finance", 80, "North America"),
    ("RetailMax", "retailmax.com", "Retail", 3500, "North America"),
    ("EduVerse", "eduverse.org", "Education", 600, "North America"),
    ("GreenEnergy Co", "greenenergy.co", "Energy", 340, "Europe"),
    ("LogiPrime", "logiprime.com", "Logistics", 900, "Europe"),
    ("DataNova Labs", "datanova.ai", "Technology", 45, "North America"),
    ("CloudBridge IO", "cloudbridge.io", "Technology", 200, "North America"),
    ("NexGen Pharma", "nexgenpharma.com", "Healthcare", 1800, "Europe"),
    ("UrbanBuild Inc", "urbanbuild.com", "Construction", 650, "North America"),
    ("SwiftLogic", "swiftlogic.dev", "Technology", 30, "Asia Pacific"),
    ("PeakForce Ltd", "peakforce.co.uk", "Manufacturing", 1200, "Europe"),
    ("SkyLane Analytics", "skylane.io", "Technology", 75, "North America"),
    ("CoreStack Inc", "corestack.com", "Technology", 150, "North America"),
    ("TrueNorth Data", "truenorth.ca", "Technology", 90, "North America"),
    ("AeroSync Ltd", "aerosync.de", "Aerospace", 400, "Europe"),
    ("VeloCity Tech", "velocity.tech", "Technology", 60, "Asia Pacific"),
    ("HexaCore Systems", "hexacore.com", "Technology", 110, "North America"),
    ("Bright Health", "brighthealth.com", "Healthcare", 500, "North America"),
    ("Atlas Freight", "atlasfreight.com", "Logistics", 1500, "North America"),
    ("Pinnacle HR", "pinnaclehr.com", "Services", 250, "Europe"),
    ("OmniWare Solutions", "omniware.io", "Technology", 85, "Asia Pacific"),
    ("FusionGrid Corp", "fusiongrid.com", "Energy", 700, "North America"),
    ("ClearPath Digital", "clearpath.co", "Marketing", "160", "North America"),
    ("EdgePoint Labs", "edgepoint.ai", "Technology", 40, "North America"),
    ("IronClad Security", "ironclad.io", "Cybersecurity", 95, "North America"),
    ("RapidScale Inc", "rapidscale.com", "Technology", 180, "Europe"),
    ("MindBridge AI", "mindbridge.ai", "Technology", 55, "North America"),
    ("Quantum Dynamics", "quantumdyn.com", "Technology", 220, "North America"),
    ("NetPulse Systems", "netpulse.com", "Telecommunications", 800, "North America"),
    ("NovaStar Systems", "novastar.io", "Technology", 130, "Asia Pacific"),
    ("BlueHorizon Tech", "bluehorizon.tech", "Technology", 70, "Europe"),
    ("TidalWave IO", "tidalwave.io", "Technology", 100, "North America"),
    ("InfiniteLoop Tech", "infiniteloop.dev", "Technology", 35, "North America"),
    ("CyberNest Inc", "cybernest.com", "Cybersecurity", 140, "North America"),
    ("NorthStar Consulting", "northstar.co", "Consulting", 300, "Europe"),
    ("GlobalSync Ltd", "globalsync.com", "Technology", 175, "Asia Pacific"),
    ("PrismView Corp", "prismview.com", "Marketing", 210, "North America"),
]

PLAN_PRICING = {
    "Free": 0,
    "Starter": 49,
    "Growth": 149,
    "Business": 399,
    "Enterprise": 1499,
}

SEAT_MULTIPLIER = {
    "Free": 0,
    "Starter": 10,
    "Growth": 25,
    "Business": 50,
    "Enterprise": 100,
}

CSM_OWNERS = [
    "Sarah Chen", "Mike Rodriguez", "Emily Park", "James Wilson",
    "Lisa Thompson", "David Kim",
]

FEATURES = [
    "dashboard", "reports", "api_access", "integrations",
    "custom_alerts", "data_export", "team_collaboration",
    "advanced_analytics", "sso", "audit_log",
]

TICKET_SUBJECTS = {
    "bug": [
        "Dashboard loading slowly", "Export fails for large datasets",
        "SSO login intermittent failure", "Chart rendering broken on Safari",
        "API timeout on bulk queries", "Notification emails not sending",
        "Duplicate data in reports", "Filter reset on page navigation",
    ],
    "feature_request": [
        "Custom dashboard widgets", "Slack integration",
        "Mobile app support", "Dark mode", "Bulk user import",
        "Scheduled report delivery", "Custom API rate limits",
    ],
    "billing": [
        "Invoice discrepancy", "Need plan downgrade",
        "Annual billing switch", "Tax exemption certificate",
        "Refund request", "Missing invoice for last month",
    ],
    "onboarding": [
        "Need help with initial setup", "Data migration assistance",
        "Team training session request", "API documentation unclear",
        "SSO configuration help", "Custom field setup",
    ],
    "integration": [
        "Salesforce sync broken", "HubSpot connector issue",
        "Slack bot not responding", "Webhook delivery failing",
        "Jira integration setup", "Google Workspace SSO",
    ],
    "performance": [
        "Slow query execution", "High API latency",
        "Dashboard timeout", "Report generation taking too long",
        "Search indexing delay", "Real-time data lag",
    ],
}


def seed_database() -> None:
    os.makedirs(DB_PATH.parent, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)

    random.seed(42)

    base_date = datetime(2024, 1, 1)
    now = datetime(2025, 6, 30)

    # ── 1. Accounts ──────────────────────────────────────────────

    accounts_data = []
    for i, (name, domain, industry, emp, region) in enumerate(COMPANIES, 1):
        emp_count = int(emp) if isinstance(emp, str) else emp
        # Assign initial plan based on company size
        if emp_count > 1000:
            plan = random.choice(["Business", "Enterprise"])
        elif emp_count > 200:
            plan = random.choice(["Growth", "Business"])
        elif emp_count > 50:
            plan = random.choice(["Starter", "Growth"])
        else:
            plan = random.choice(["Free", "Starter"])

        # Calculate MRR based on plan + seats
        base_mrr = PLAN_PRICING[plan]
        seats = max(1, emp_count // 10) if plan != "Free" else 0
        seat_cost = SEAT_MULTIPLIER.get(plan, 0)
        mrr = base_mrr + (seats * seat_cost) if plan != "Free" else 0

        # Signup date: spread across 18 months
        signup_offset = random.randint(0, 450)
        signup_date = (base_date + timedelta(days=signup_offset)).strftime("%Y-%m-%d")

        # ~15% churn rate
        status = "active"
        churn_date = None
        if random.random() < 0.15 and plan != "Free":
            status = "churned"
            churn_offset = random.randint(60, 400)
            churn_dt = base_date + timedelta(days=signup_offset + churn_offset)
            if churn_dt < now:
                churn_date = churn_dt.strftime("%Y-%m-%d")
            else:
                status = "active"
                churn_date = None
        elif plan == "Free" and random.random() < 0.3:
            status = "trial"

        csm = random.choice(CSM_OWNERS) if plan in ("Business", "Enterprise") else None

        cursor.execute(
            "INSERT INTO accounts (id, company_name, domain, plan, mrr, status, "
            "industry, employee_count, signup_date, churn_date, region, csm_owner) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, name, domain, plan, round(mrr, 2), status, industry,
             emp_count, signup_date, churn_date, region, csm),
        )
        accounts_data.append({
            "id": i, "plan": plan, "mrr": mrr, "status": status,
            "signup_date": signup_date, "seats": seats,
        })

    num_accounts = len(COMPANIES)

    # ── 2. Subscriptions ─────────────────────────────────────────

    sub_id = 1
    for acct in accounts_data:
        if acct["plan"] == "Free":
            continue

        billing = "annual" if random.random() < 0.4 else "monthly"
        cursor.execute(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sub_id, acct["id"], acct["plan"], round(acct["mrr"], 2),
             acct["seats"], acct["signup_date"], None, 1, billing),
        )
        sub_id += 1

        # ~30% of accounts had a plan change (upgrade or downgrade)
        if random.random() < 0.30:
            plans = list(PLAN_PRICING.keys())
            current_idx = plans.index(acct["plan"])
            if random.random() < 0.75 and current_idx < len(plans) - 1:
                new_plan = plans[current_idx + 1]  # upgrade
            elif current_idx > 1:
                new_plan = plans[current_idx - 1]  # downgrade
            else:
                continue

            change_date = datetime.strptime(acct["signup_date"], "%Y-%m-%d")
            change_date += timedelta(days=random.randint(30, 180))
            if change_date >= now:
                continue

            new_mrr = PLAN_PRICING[new_plan] + (acct["seats"] * SEAT_MULTIPLIER.get(new_plan, 0))
            # End old subscription
            cursor.execute(
                "UPDATE subscriptions SET ended_at = ?, is_current = 0 WHERE id = ?",
                (change_date.strftime("%Y-%m-%d"), sub_id - 1),
            )
            # New subscription
            cursor.execute(
                "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sub_id, acct["id"], new_plan, round(new_mrr, 2),
                 acct["seats"], change_date.strftime("%Y-%m-%d"), None, 1,
                 billing),
            )
            sub_id += 1

    # ── 3. MRR Events ────────────────────────────────────────────

    mrr_id = 1
    for acct in accounts_data:
        if acct["plan"] == "Free":
            continue

        # New business event
        cursor.execute(
            "INSERT INTO mrr_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mrr_id, acct["id"], "new", round(acct["mrr"], 2), 0,
             round(acct["mrr"], 2), acct["signup_date"], "New signup"),
        )
        mrr_id += 1

        # Random expansion/contraction events
        current_mrr = acct["mrr"]
        event_date = datetime.strptime(acct["signup_date"], "%Y-%m-%d")

        for _ in range(random.randint(0, 3)):
            event_date += timedelta(days=random.randint(30, 120))
            if event_date >= now:
                break

            if random.random() < 0.65:  # 65% expansion
                delta = round(current_mrr * random.uniform(0.1, 0.5), 2)
                new_mrr = round(current_mrr + delta, 2)
                reasons = [
                    "Added seats", "Plan upgrade", "Add-on purchase",
                    "Volume increase", "Premium feature adoption",
                ]
                cursor.execute(
                    "INSERT INTO mrr_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (mrr_id, acct["id"], "expansion", delta, current_mrr,
                     new_mrr, event_date.strftime("%Y-%m-%d"),
                     random.choice(reasons)),
                )
                current_mrr = new_mrr
            else:  # 35% contraction
                delta = round(current_mrr * random.uniform(0.05, 0.25), 2)
                new_mrr = round(current_mrr - delta, 2)
                reasons = [
                    "Removed seats", "Plan downgrade", "Budget cut",
                    "Reduced usage",
                ]
                cursor.execute(
                    "INSERT INTO mrr_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (mrr_id, acct["id"], "contraction", -delta, current_mrr,
                     new_mrr, event_date.strftime("%Y-%m-%d"),
                     random.choice(reasons)),
                )
                current_mrr = new_mrr
            mrr_id += 1

        # Churn event if applicable
        if acct["status"] == "churned":
            churn_reasons = [
                "Switched to competitor", "Budget constraints",
                "Product didn't meet needs", "Company acquired",
                "Lack of key features",
            ]
            cursor.execute(
                "INSERT INTO mrr_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mrr_id, acct["id"], "churn", -current_mrr, current_mrr,
                 0, acct.get("churn_date", now.strftime("%Y-%m-%d")),
                 random.choice(churn_reasons)),
            )
            mrr_id += 1

    # ── 4. Feature Usage (daily, last 90 days) ───────────────────

    usage_id = 1
    for day_offset in range(90):
        date = (now - timedelta(days=89 - day_offset)).strftime("%Y-%m-%d")
        # Sample ~15 accounts per day to keep data manageable
        sampled = random.sample(range(1, num_accounts + 1), min(15, num_accounts))

        for acct_id in sampled:
            acct = accounts_data[acct_id - 1]
            if acct["status"] == "churned":
                continue

            num_features = random.randint(2, 6)
            used_features = random.sample(FEATURES, num_features)

            for feature in used_features:
                dau = random.randint(1, max(1, acct["seats"]))
                events = dau * random.randint(5, 50)
                cursor.execute(
                    "INSERT INTO feature_usage VALUES (?, ?, ?, ?, ?, ?)",
                    (usage_id, acct_id, feature, dau, events, date),
                )
                usage_id += 1

    # ── 5. Support Tickets ───────────────────────────────────────

    ticket_id = 1
    for day_offset in range(450):
        date = base_date + timedelta(days=day_offset)
        if date > now:
            break

        # 2-6 tickets per day
        daily_tickets = random.randint(2, 6)
        for _ in range(daily_tickets):
            acct_id = random.randint(1, num_accounts)
            category = random.choice(list(TICKET_SUBJECTS.keys()))
            subject = random.choice(TICKET_SUBJECTS[category])
            priority = random.choices(
                ["low", "medium", "high", "critical"],
                weights=[30, 40, 20, 10],
            )[0]

            created = date + timedelta(
                hours=random.randint(8, 18),
                minutes=random.randint(0, 59),
            )

            # Resolution
            days_ago = (now - date).days
            if days_ago > 7:
                status = random.choices(
                    ["resolved", "closed"],
                    weights=[60, 40],
                )[0]
                resolve_hours = random.randint(1, 72)
                resolved_at = (created + timedelta(hours=resolve_hours)).strftime(
                    "%Y-%m-%d %H:%M"
                )
                first_response = random.randint(5, 120)
                csat = random.choices([1, 2, 3, 4, 5], weights=[3, 5, 15, 40, 37])[0]
            elif days_ago > 1:
                status = random.choice(["in_progress", "resolved"])
                resolved_at = None
                first_response = random.randint(5, 60)
                csat = None
                if status == "resolved":
                    resolved_at = (
                        created + timedelta(hours=random.randint(2, 48))
                    ).strftime("%Y-%m-%d %H:%M")
                    csat = random.choices([3, 4, 5], weights=[15, 40, 45])[0]
            else:
                status = "open"
                resolved_at = None
                first_response = None
                csat = None

            cursor.execute(
                "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ticket_id, acct_id, subject, priority, category, status,
                 created.strftime("%Y-%m-%d %H:%M"), resolved_at,
                 first_response, csat),
            )
            ticket_id += 1

    # ── 6. Invoices ──────────────────────────────────────────────

    invoice_id = 1
    for acct in accounts_data:
        if acct["plan"] == "Free" or acct["mrr"] == 0:
            continue

        start = datetime.strptime(acct["signup_date"], "%Y-%m-%d")
        month = start.replace(day=1)

        while month < now:
            issue_date = month
            due_date = month + timedelta(days=30)
            inv_number = f"INV-{issue_date.strftime('%Y%m')}-{invoice_id:05d}"

            # Determine status
            days_since = (now - issue_date).days
            if days_since > 45:
                inv_status = random.choices(
                    ["paid", "paid", "paid", "overdue"],
                    weights=[80, 5, 5, 10],
                )[0]
                paid_date = (
                    (issue_date + timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")
                    if inv_status == "paid"
                    else None
                )
            elif days_since > 15:
                inv_status = "sent"
                paid_date = None
            else:
                inv_status = "draft"
                paid_date = None

            cursor.execute(
                "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, acct["id"], inv_number, round(acct["mrr"], 2),
                 inv_status, issue_date.strftime("%Y-%m-%d"),
                 due_date.strftime("%Y-%m-%d"), paid_date),
            )
            invoice_id += 1

            # Next month
            if month.month == 12:
                month = month.replace(year=month.year + 1, month=1)
            else:
                month = month.replace(month=month.month + 1)

    conn.commit()

    # Print summary
    print()
    for table in [
        "accounts", "subscriptions", "mrr_events",
        "feature_usage", "support_tickets", "invoices",
    ]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rows")

    # Print key metrics
    total_mrr = cursor.execute(
        "SELECT SUM(mrr) FROM accounts WHERE status = 'active'"
    ).fetchone()[0]
    active = cursor.execute(
        "SELECT COUNT(*) FROM accounts WHERE status = 'active'"
    ).fetchone()[0]
    churned = cursor.execute(
        "SELECT COUNT(*) FROM accounts WHERE status = 'churned'"
    ).fetchone()[0]

    print(f"\n  Total MRR: ${total_mrr:,.2f}")
    print(f"  Active accounts: {active}")
    print(f"  Churned accounts: {churned}")
    print(f"  Churn rate: {churned / (active + churned) * 100:.1f}%")

    conn.close()
    print(f"\n  Database: {DB_PATH}")


if __name__ == "__main__":
    print("Seeding DataPilot SaaS metrics database...")
    seed_database()
    print("\nDone!")
