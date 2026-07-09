#!/usr/bin/env python3
"""
Generate a large synthetic CSV dataset (1M+ records) for ReturnShieldAI import.

Usage:
    python -m app.scripts.generate_large_dataset --rows 1000000 --output data/large_returns.csv
"""

import argparse
import csv
import logging
import os
import random
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("generate_dataset")

NAMES = [
    "Alice Johnson", "Bob Smith", "Carol White", "Dave Brown", "Eve Davis",
    "Frank Miller", "Grace Wilson", "Hank Moore", "Ivy Taylor", "Jack Anderson",
    "Kate Thomas", "Leo Jackson", "Mia Martin", "Nick Lee", "Oscar Harris",
    "Paula Clark", "Quinn Lewis", "Rachel Walker", "Sam Hall", "Tina Allen",
]
PRODUCTS = [
    ("SKU-001", "Designer Jacket", "apparel", 420.00, 0.8),
    ("SKU-002", "Wireless Earbuds", "electronics", 199.99, 0.1),
    ("SKU-003", "Cashmere Sweater", "apparel", 180.00, 0.4),
    ("SKU-004", "Bluetooth Speaker", "electronics", 89.99, 0.6),
    ("SKU-005", "Running Shoes", "footwear", 150.00, 0.7),
    ("SKU-006", "Smart Watch", "electronics", 350.00, 0.2),
    ("SKU-007", "Leather Bag", "accessories", 280.00, 0.5),
    ("SKU-008", "Yoga Mat", "sports", 45.00, 0.9),
    ("SKU-009", "Coffee Maker", "home", 79.99, 1.2),
    ("SKU-010", "Desk Lamp", "home", 55.00, 0.6),
]
REASONS = [
    "Changed mind", "Wrong size", "Defective item", "Not as described",
    "Arrived damaged", "Better price elsewhere", "Ordered by mistake",
    "Quality not satisfactory", "Missing parts", "Late delivery",
]
CARRIERS = ["UPS", "FedEx", "USPS", "DHL", "Canada Post"]
PAYMENT_METHODS = ["card", "paypal", "upi", "bank_transfer"]
CONDITIONS = ["new", "like_new", "good", "fair", "damaged"]
FRAUD_REASONS = [
    "Box arrived empty, request full refund",
    "Item not received but tracking shows delivered",
    "Returning empty box, item removed",
    "Wrong item received (different brand)",
    "Item damaged during unboxing",
]
FRAUD_SKU_WEIGHTS = {s[0]: s[4] for s in PRODUCTS}


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def generate_row(customer_idx: int, order_idx: int, fraud_rate: float) -> dict:
    is_fraud = random.random() < fraud_rate
    name = random.choice(NAMES)
    sku, product_name, category, price, weight = random.choice(PRODUCTS)

    if is_fraud:
        reason = random.choice(FRAUD_REASONS)
        returned_weight = round(random.uniform(0.05, weight * 0.3), 3)
        chargeback = "true" if random.random() < 0.3 else "false"
        condition = random.choice(["damaged", "fair"])
        delivery_days = random.randint(1, 3)
        return_days = random.randint(0, 1)
    else:
        reason = random.choice(REASONS)
        returned_weight = round(random.uniform(weight * 0.9, weight * 1.1), 3)
        chargeback = "false"
        condition = random.choice(["new", "like_new", "good"])
        delivery_days = random.randint(3, 10)
        return_days = random.randint(2, 30)

    order_date = random_date(datetime(2025, 1, 1), datetime(2026, 6, 30))
    delivery_date = order_date + timedelta(days=delivery_days)
    return_date = delivery_date + timedelta(days=return_days)
    support_text = (
        f"Customer reports: {reason.lower()}. "
        f"Order #{order_idx} was delivered on {delivery_date.strftime('%Y-%m-%d')}."
        if random.random() < 0.4 else ""
    )

    return {
        "customer_id": f"CUST-{customer_idx:06d}",
        "customer_name": name,
        "customer_email": f"{name.lower().replace(' ', '.')}@example.com",
        "customer_phone": f"+1-555-{random.randint(100,999):03d}-{random.randint(1000,9999):04d}",
        "order_id": f"ORD-{order_idx:07d}",
        "order_date": order_date.strftime("%Y-%m-%d"),
        "sku": sku,
        "product_name": product_name,
        "category": category,
        "product_value": f"{price:.2f}",
        "quantity": str(random.randint(1, 2)),
        "payment_method": random.choice(PAYMENT_METHODS),
        "return_reason": reason,
        "return_date": return_date.strftime("%Y-%m-%d"),
        "delivery_date": delivery_date.strftime("%Y-%m-%d"),
        "expected_weight": f"{weight:.3f}",
        "returned_weight": f"{returned_weight:.3f}",
        "carrier": random.choice(CARRIERS),
        "tracking_number": f"TRK-{random.randint(100000000, 999999999)}",
        "address": f"{random.randint(1, 9999)} {random.choice(['Oak', 'Elm', 'Maple', 'Pine', 'Cedar'])} St",
        "device_id": f"DEV-{random.randint(1000, 9999)}" if random.random() < 0.7 else "",
        "ip_address": f"{random.randint(10, 223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "payment_token": f"tok_{random.randint(100000, 999999)}" if random.random() < 0.8 else "",
        "refund_account": f"acct_{random.randint(10000, 99999)}" if random.random() < 0.3 else "",
        "return_condition": condition,
        "chargeback": chargeback,
        "support_text": support_text,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate large synthetic return dataset")
    parser.add_argument("--rows", type=int, default=1_000_000, help="Number of rows (default 1M)")
    parser.add_argument("--output", default="data/large_returns.csv", help="Output CSV path")
    parser.add_argument("--fraud-rate", type=float, default=0.08, help="Fraud rate (0-1)")
    parser.add_argument("--unique-customers", type=int, default=50000, help="Unique customer count")
    args = parser.parse_args()

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    columns = [
        "customer_id", "customer_name", "customer_email", "customer_phone",
        "order_id", "order_date", "sku", "product_name", "category",
        "product_value", "quantity", "payment_method", "return_reason",
        "return_date", "delivery_date", "expected_weight", "returned_weight",
        "carrier", "tracking_number", "address", "device_id", "ip_address",
        "payment_token", "refund_account", "return_condition", "chargeback",
        "support_text",
    ]

    logger.info("Generating %s records with %d unique customers → %s",
                f"{args.rows:,}", args.unique_customers, output_path)

    start = time.time()
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        BATCH_LOG = max(1, args.rows // 20)
        customers = [random.randint(1, args.unique_customers) for _ in range(args.rows)]

        for i in range(1, args.rows + 1):
            row = generate_row(customers[i - 1], i, args.fraud_rate)
            writer.writerow(row)

            if i % BATCH_LOG == 0:
                pct = i / args.rows * 100
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                logger.info("  %6.1f%% | %s rows | %s rows/sec",
                            pct, f"{i:,}", f"{rate:,.0f}")

    elapsed = time.time() - start
    size = os.path.getsize(output_path)
    logger.info("Done! %s rows written to %s (%s) in %.1fs",
                f"{args.rows:,}", output_path, format_bytes(size), elapsed)


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


if __name__ == "__main__":
    main()
