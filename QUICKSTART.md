# Quick Start Guide

Get the DQ Pipeline up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available for Docker
- Ports 8000 and 9092 available

## Step 1: Start the Pipeline

```bash
cd dq-pipeline
docker-compose up --build
```

Wait for all services to start (approximately 30-60 seconds). You'll see logs from:
- Zookeeper
- Kafka
- Validator service
- DQ Report service

## Step 2: Verify Services

Open a new terminal and check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "consumer": "running",
  "total_violations": 0
}
```

## Step 3: Send Test Messages

### Option A: Using Python Script

```bash
# Install kafka-python
pip install kafka-python

# Run the sample data producer
python produce_sample_data.py
```

### Option B: Using Kafka Console Producer

```bash
# Produce a valid customer
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic raw.customers

# Paste this JSON and press Enter:
{"id":"CUST-123456","name":"John Doe","email":"john@example.com","age":30,"signup_date":"2024-01-20","status":"active"}
```

## Step 4: Check Results

### View Violations Report

```bash
curl http://localhost:8000/dq-report
```

### View Top Violations

```bash
curl "http://localhost:8000/dq-top-violations?hours=24&limit=5"
```

### View Sample Violations for Customers

```bash
curl "http://localhost:8000/dq-sample?domain=customers&limit=10"
```

## Step 5: Monitor Logs

### View Validator Logs

```bash
docker-compose logs -f validator
```

### View DQ Report Logs

```bash
docker-compose logs -f dq_report
```

### View Kafka Topics

```bash
# List all topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# Consume from valid.customers
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic valid.customers \
  --from-beginning
```

## Common Test Scenarios

### 1. Valid Customer (Should Pass)

```json
{
  "id": "CUST-123456",
  "name": "John Doe",
  "email": "john@example.com",
  "age": 30,
  "signup_date": "2024-01-20",
  "status": "active"
}
```

### 2. Invalid Customer - Age < 18 (Business Rule Violation)

```json
{
  "id": "CUST-123457",
  "name": "Jane Smith",
  "email": "jane@example.com",
  "age": 16,
  "signup_date": "2024-01-20"
}
```

### 3. Invalid Customer - Bad Email Domain (Business Rule Violation)

```json
{
  "id": "CUST-123458",
  "name": "Bob Jones",
  "email": "bob@tempmail.com",
  "age": 25,
  "signup_date": "2024-01-20"
}
```

### 4. Invalid Customer - Bad ID Format (Schema Violation)

```json
{
  "id": "INVALID-ID",
  "name": "Alice Brown",
  "email": "alice@example.com",
  "age": 28,
  "signup_date": "2024-01-20"
}
```

### 5. Valid Order (Should Pass)

```json
{
  "order_id": "ORD-12345678",
  "customer_id": "CUST-123456",
  "order_total": 99.99,
  "items_count": 3,
  "order_date": "2024-01-20T10:30:00Z"
}
```

### 6. Invalid Order - Zero Total (Business Rule Violation)

```json
{
  "order_id": "ORD-12345679",
  "customer_id": "CUST-123456",
  "order_total": 0,
  "items_count": 1,
  "order_date": "2024-01-20T10:30:00Z"
}
```

## Troubleshooting

### Services won't start

```bash
# Check Docker resources
docker info

# Restart Docker
# Then try again:
docker-compose down -v
docker-compose up --build
```

### Port conflicts

If ports 8000 or 9092 are in use, modify `docker-compose.yml`:

```yaml
# Change API port
dq_report:
  ports:
    - "8001:8000"  # Use 8001 instead

# Change Kafka port
kafka:
  ports:
    - "9093:9092"  # Use 9093 instead
```

### No violations showing up

Wait a few seconds for processing, then check:

```bash
# Check validator is processing
docker-compose logs validator | grep "Processing message"

# Check consumer is running
curl http://localhost:8000/health
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Review [DESIGN.md](DESIGN.md) for architecture details
- Run integration tests: `python tests/test_integration.py`
- Add your own schemas in `contracts/`
- Add your own rules in `rules/business_rules.yml`

## Stopping the Pipeline

```bash
# Stop services
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v
```

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /` | Service information |
| `GET /health` | Health check |
| `GET /dq-report` | Aggregated violations report |
| `GET /dq-top-violations` | Top N violations |
| `GET /dq-sample?domain={domain}` | Sample violations for domain |
| `GET /dq-stats` | Overall statistics |

Enjoy your Data Quality Pipeline! 🚀
