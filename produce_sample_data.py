#!/usr/bin/env python3
"""
Sample data producer for testing the DQ pipeline.
"""
import json
from kafka import KafkaProducer
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Valid customer
valid_customer = {
    "id": "CUST-123456",
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30,
    "signup_date": "2024-01-20",
    "status": "active"
}
producer.send('raw.customers', value=valid_customer)
print(f"✓ Sent valid customer: {valid_customer['id']}")

# Invalid customer (age < 18)
invalid_customer = {
    "id": "CUST-123457",
    "name": "Jane Smith",
    "email": "jane@example.com",
    "age": 16,
    "signup_date": "2024-01-20"
}
producer.send('raw.customers', value=invalid_customer)
print(f"✓ Sent invalid customer: {invalid_customer['id']}")

# Valid order
valid_order = {
    "order_id": "ORD-12345678",
    "customer_id": "CUST-123456",
    "order_total": 99.99,
    "items_count": 3,
    "order_date": datetime.now().isoformat() + "Z"
}
producer.send('raw.orders', value=valid_order)
print(f"✓ Sent valid order: {valid_order['order_id']}")

# Invalid order (total = 0)
invalid_order = {
    "order_id": "ORD-12345679",
    "customer_id": "CUST-123456",
    "order_total": 0,
    "items_count": 1,
    "order_date": datetime.now().isoformat() + "Z"
}
producer.send('raw.orders', value=invalid_order)
print(f"✓ Sent invalid order: {invalid_order['order_id']}")

producer.flush()
producer.close()
print("\n✓ All messages sent successfully!")
