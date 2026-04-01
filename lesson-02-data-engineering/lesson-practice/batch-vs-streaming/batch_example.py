import time
from datetime import datetime


def generate_orders(count: int = 20) -> list[dict]:
    orders = []
    for i in range(count):
        orders.append({
            "id": i + 1,
            "product": f"Product-{chr(65 + i % 5)}",
            "amount": round(10 + i * 7.5, 2),
            "timestamp": datetime.now().isoformat(),
        })
        time.sleep(0.1)
    return orders


def process_batch(orders: list[dict]) -> dict:
    total = sum(o["amount"] for o in orders)
    by_product = {}
    for o in orders:
        by_product[o["product"]] = by_product.get(o["product"], 0) + o["amount"]
    return {"total_orders": len(orders), "total_revenue": total, "by_product": by_product}


def save_report(report: dict):
    print(f"  Total orders:  {report['total_orders']}")
    print(f"  Total revenue: ${report['total_revenue']:,.2f}")
    for product, revenue in report["by_product"].items():
        print(f"    {product}: ${revenue:,.2f}")


if __name__ == "__main__":
    print("[BATCH] Збираємо замовлення...")
    orders = generate_orders(20)
    print(f"[BATCH] Зібрано {len(orders)} замовлень\n")

    print("[BATCH] Обробляємо всю пачку...")
    report = process_batch(orders)

    print("[BATCH] Результат:\n")
    save_report(report)
