"""Mock e-commerce data — customers, orders, fraud signals, refund cases."""

CUSTOMERS = {
    "C-1001": {
        "customer_id": "C-1001",
        "name": "John Doe",
        "email": "john@example.com",
        "tenure_years": 3.4,
        "total_orders": 47,
        "total_refunds": 2,
        "lifetime_value_usd": 2840,
    },
    "C-1002": {
        "customer_id": "C-1002",
        "name": "Maria Schmidt",
        "email": "maria.s@example.com",
        "tenure_years": 0.2,
        "total_orders": 1,
        "total_refunds": 0,
        "lifetime_value_usd": 320,
    },
    "C-1003": {
        "customer_id": "C-1003",
        "name": "Alex Petrov",
        "email": "alex.p@example.com",
        "tenure_years": 0.1,
        "total_orders": 6,
        "total_refunds": 5,
        "lifetime_value_usd": 1200,
    },
    "C-1004": {
        "customer_id": "C-1004",
        "name": "Sara Lee",
        "email": "sara.l@example.com",
        "tenure_years": 2.1,
        "total_orders": 18,
        "total_refunds": 1,
        "lifetime_value_usd": 540,
    },
}

ORDERS = {
    "O-9001": {
        "order_id": "O-9001",
        "customer_id": "C-1001",
        "amount_usd": 45,
        "items": ["Wireless mouse"],
        "shipped": True,
        "delivered": False,
        "carrier_status": "lost in transit",
        "days_since_order": 14,
    },
    "O-9002": {
        "order_id": "O-9002",
        "customer_id": "C-1002",
        "amount_usd": 320,
        "items": ["Ceramic vase set"],
        "shipped": True,
        "delivered": True,
        "carrier_status": "delivered",
        "days_since_order": 5,
    },
    "O-9003": {
        "order_id": "O-9003",
        "customer_id": "C-1003",
        "amount_usd": 1200,
        "items": ["Designer handbag"],
        "shipped": True,
        "delivered": True,
        "carrier_status": "delivered",
        "days_since_order": 8,
    },
    "O-9004": {
        "order_id": "O-9004",
        "customer_id": "C-1004",
        "amount_usd": 89,
        "items": ["Streaming subscription (annual)"],
        "shipped": False,
        "delivered": False,
        "carrier_status": "digital",
        "days_since_order": 32,
    },
}

FRAUD_SIGNALS = {
    "C-1001": {"score": 0.05, "flags": []},
    "C-1002": {"score": 0.20, "flags": ["new_account"]},
    "C-1003": {
        "score": 0.78,
        "flags": [
            "new_account_under_60d",
            "5_refunds_in_30d",
            "high_value_disputes",
            "ip_geolocation_mismatch",
        ],
    },
    "C-1004": {"score": 0.35, "flags": ["expired_card_on_file", "policy_unclear"]},
}

CASES = [
    {
        "case_id": "RF-001",
        "label": "RF-001 · Lost package · $45",
        "customer_id": "C-1001",
        "order_id": "O-9001",
        "reason": "Package marked as lost by carrier 14 days ago. Never received.",
        "amount_requested_usd": 45,
        "channel": "email",
    },
    {
        "case_id": "RF-002",
        "label": "RF-002 · Damaged item · $320",
        "customer_id": "C-1002",
        "order_id": "O-9002",
        "reason": "Vase arrived broken. No photo provided initially. New customer.",
        "amount_requested_usd": 320,
        "channel": "chat",
    },
    {
        "case_id": "RF-003",
        "label": "RF-003 · 'Not as described' · $1,200",
        "customer_id": "C-1003",
        "order_id": "O-9003",
        "reason": "Customer claims handbag is not as described. High refund history.",
        "amount_requested_usd": 1200,
        "channel": "phone",
    },
    {
        "case_id": "RF-004",
        "label": "RF-004 · Subscription dispute · $89",
        "customer_id": "C-1004",
        "order_id": "O-9004",
        "reason": "Customer disputes annual renewal charge. Card on file expired.",
        "amount_requested_usd": 89,
        "channel": "email",
    },
]


def get_case(case_id: str) -> dict:
    for c in CASES:
        if c["case_id"] == case_id:
            return c
    raise KeyError(case_id)
