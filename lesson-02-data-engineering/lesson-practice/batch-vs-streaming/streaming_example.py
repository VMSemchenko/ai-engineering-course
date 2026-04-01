import time
import random
import threading
from datetime import datetime
from queue import Queue


order_queue: Queue = Queue()


def source(count: int = 15):
    for i in range(count):
        order = {
            "id": i + 1,
            "product": f"Product-{chr(65 + i % 5)}",
            "amount": round(10 + random.uniform(0, 100), 2),
            "timestamp": datetime.now().isoformat(),
        }
        order_queue.put(order)
        print(f"  [SOURCE]  Нове замовлення #{order['id']}: {order['product']} ${order['amount']}")
        time.sleep(random.uniform(0.2, 0.8))

    order_queue.put(None)


def process_and_deliver():
    total = 0
    count = 0

    while True:
        order = order_queue.get()
        if order is None:
            break

        total += order["amount"]
        count += 1
        avg = total / count

        print(f"  [STREAM]  -> Оброблено #{order['id']} | "
              f"Running total: ${total:,.2f} | Avg: ${avg:,.2f} | Count: {count}")

    print(f"\n  [DONE] Всього: {count} замовлень, ${total:,.2f}")


if __name__ == "__main__":
    print("[STREAMING] Запуск real-time обробки...\n")

    source_thread = threading.Thread(target=source, args=(15,))
    source_thread.start()

    process_and_deliver()
    source_thread.join()
