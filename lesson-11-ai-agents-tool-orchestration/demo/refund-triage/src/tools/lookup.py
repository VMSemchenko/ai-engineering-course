"""Read-only tools — agent can always call these."""

from data.fixtures import CUSTOMERS, ORDERS, FRAUD_SIGNALS


def lookup_customer(customer_id: str) -> dict:
    return CUSTOMERS.get(customer_id, {"error": f"customer {customer_id} not found"})


def lookup_order(order_id: str) -> dict:
    return ORDERS.get(order_id, {"error": f"order {order_id} not found"})


def get_fraud_signals(customer_id: str) -> dict:
    return FRAUD_SIGNALS.get(customer_id, {"score": 0.0, "flags": []})
