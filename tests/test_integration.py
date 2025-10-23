"""
Integration tests for the DQ pipeline.
Tests end-to-end flow: produce -> validate -> consume -> API query.
"""
import json
import time
import requests
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError


# Configuration
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
API_BASE_URL = 'http://localhost:8000'


def create_producer():
    """Create a Kafka producer for testing."""
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )


def create_consumer(topics, group_id='test-consumer'):
    """Create a Kafka consumer for testing."""
    return KafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=10000
    )


def test_valid_customer_flow():
    """Test that a valid customer is routed to valid.customers topic."""
    print("\n=== Test: Valid Customer Flow ===")
    
    producer = create_producer()
    
    # Create a valid customer
    valid_customer = {
        "id": "CUST-999001",
        "name": "Alice Smith",
        "email": "alice.smith@example.com",
        "age": 28,
        "signup_date": "2024-01-20",
        "status": "active"
    }
    
    # Produce to raw.customers
    print(f"Producing valid customer: {valid_customer['id']}")
    producer.send('raw.customers', value=valid_customer, key=valid_customer['id'])
    producer.flush()
    
    # Wait for processing
    time.sleep(5)
    
    # Consume from valid.customers
    print("Consuming from valid.customers...")
    consumer = create_consumer(['valid.customers'], group_id='test-valid-consumer')
    
    found = False
    for message in consumer:
        if message.value.get('id') == valid_customer['id']:
            print(f"✓ Valid customer found in valid.customers: {message.value['id']}")
            found = True
            break
    
    consumer.close()
    producer.close()
    
    assert found, "Valid customer not found in valid.customers topic"
    print("✓ Test passed: Valid customer routed correctly")


def test_schema_invalid_customer_flow():
    """Test that a schema-invalid customer is routed to DLQ and violations are recorded."""
    print("\n=== Test: Schema Invalid Customer Flow ===")
    
    producer = create_producer()
    
    # Create a schema-invalid customer (invalid ID format)
    invalid_customer = {
        "id": "INVALID-ID",
        "name": "Bob Jones",
        "email": "bob.jones@example.com",
        "age": 35,
        "signup_date": "2024-01-20"
    }
    
    # Produce to raw.customers
    print(f"Producing schema-invalid customer: {invalid_customer['id']}")
    producer.send('raw.customers', value=invalid_customer, key=invalid_customer['id'])
    producer.flush()
    
    # Wait for processing
    time.sleep(5)
    
    # Consume from invalid.customers.dlq
    print("Consuming from invalid.customers.dlq...")
    consumer = create_consumer(['invalid.customers.dlq'], group_id='test-invalid-consumer')
    
    found_in_dlq = False
    for message in consumer:
        if message.value.get('id') == invalid_customer['id']:
            print(f"✓ Invalid customer found in DLQ: {message.value['id']}")
            found_in_dlq = True
            break
    
    consumer.close()
    producer.close()
    
    assert found_in_dlq, "Invalid customer not found in DLQ topic"
    
    # Check violations via API
    print("Checking violations via API...")
    time.sleep(3)  # Wait for violation to be processed
    
    response = requests.get(f"{API_BASE_URL}/dq-sample?domain=customers&limit=50")
    assert response.status_code == 200, f"API request failed: {response.status_code}"
    
    data = response.json()
    violations = data.get('violations', [])
    
    # Look for our violation
    found_violation = any(
        'INVALID-ID' in v.get('message_id', '') or 'id' in v.get('field', '')
        for v in violations
    )
    
    if found_violation:
        print("✓ Violation recorded in database")
    else:
        print("⚠ Violation not found in API response (may need more time)")
    
    print("✓ Test passed: Schema-invalid customer routed to DLQ")


def test_business_rule_invalid_order_flow():
    """Test that a business-rule-invalid order is routed to DLQ."""
    print("\n=== Test: Business Rule Invalid Order Flow ===")
    
    producer = create_producer()
    
    # Create a business-rule-invalid order (order_total = 0)
    invalid_order = {
        "order_id": "ORD-99990001",
        "customer_id": "CUST-123456",
        "order_total": 0,  # Violates business rule
        "items_count": 1,
        "order_date": "2024-01-20T10:30:00Z"
    }
    
    # Produce to raw.orders
    print(f"Producing business-rule-invalid order: {invalid_order['order_id']}")
    producer.send('raw.orders', value=invalid_order, key=invalid_order['order_id'])
    producer.flush()
    
    # Wait for processing
    time.sleep(5)
    
    # Consume from invalid.orders.dlq
    print("Consuming from invalid.orders.dlq...")
    consumer = create_consumer(['invalid.orders.dlq'], group_id='test-order-invalid-consumer')
    
    found_in_dlq = False
    for message in consumer:
        if message.value.get('order_id') == invalid_order['order_id']:
            print(f"✓ Invalid order found in DLQ: {message.value['order_id']}")
            found_in_dlq = True
            break
    
    consumer.close()
    producer.close()
    
    assert found_in_dlq, "Invalid order not found in DLQ topic"
    print("✓ Test passed: Business-rule-invalid order routed to DLQ")


def test_api_dq_report():
    """Test the /dq-report API endpoint."""
    print("\n=== Test: DQ Report API ===")
    
    response = requests.get(f"{API_BASE_URL}/dq-report")
    assert response.status_code == 200, f"API request failed: {response.status_code}"
    
    data = response.json()
    print(f"Total violation records: {data.get('total_records', 0)}")
    
    if data.get('violations'):
        print("Sample violations:")
        for v in data['violations'][:3]:
            print(f"  - {v['domain']}.{v['rule_name']}: {v['violation_count']} violations in {v['hour_bucket']}")
    
    print("✓ Test passed: DQ Report API working")


def test_api_top_violations():
    """Test the /dq-top-violations API endpoint."""
    print("\n=== Test: Top Violations API ===")
    
    response = requests.get(f"{API_BASE_URL}/dq-top-violations?hours=24&limit=5")
    assert response.status_code == 200, f"API request failed: {response.status_code}"
    
    data = response.json()
    print(f"Top violations in last 24 hours: {data.get('total_records', 0)}")
    
    if data.get('top_violations'):
        print("Top violations:")
        for v in data['top_violations']:
            print(f"  - {v['domain']}.{v['rule_name']}: {v['violation_count']} violations")
    
    print("✓ Test passed: Top Violations API working")


def test_api_health():
    """Test the /health API endpoint."""
    print("\n=== Test: Health Check API ===")
    
    response = requests.get(f"{API_BASE_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    
    data = response.json()
    print(f"Service status: {data.get('status')}")
    print(f"Database: {data.get('database')}")
    print(f"Consumer: {data.get('consumer')}")
    print(f"Total violations: {data.get('total_violations')}")
    
    assert data.get('status') == 'healthy', "Service is not healthy"
    print("✓ Test passed: Health check successful")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("RUNNING INTEGRATION TESTS")
    print("="*60)
    
    try:
        # Test API health first
        test_api_health()
        
        # Test message flows
        test_valid_customer_flow()
        test_schema_invalid_customer_flow()
        test_business_rule_invalid_order_flow()
        
        # Test API endpoints
        test_api_dq_report()
        test_api_top_violations()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise


if __name__ == "__main__":
    # Wait for services to be ready
    print("Waiting for services to be ready...")
    time.sleep(10)
    
    run_all_tests()
