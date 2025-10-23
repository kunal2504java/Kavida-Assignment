# Data Quality Pipeline

A production-ready, event-driven data quality pipeline built with Python, Kafka, and FastAPI. This system validates incoming data against JSON schemas and business rules, routes valid/invalid messages appropriately, and provides a REST API for querying data quality violations.

## Architecture Overview

The DQ pipeline consists of the following components:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Producer  │────▶│ raw.* topics │────▶│  Validator  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌────────────────────────────┴────────────────┐
                    ▼                                              ▼
            ┌───────────────┐                            ┌─────────────────┐
            │ valid.* topics│                            │ invalid.*.dlq   │
            └───────────────┘                            └────────┬────────┘
                                                                  │
                                                         ┌────────▼─────────┐
                                                         │ dq.violations    │
                                                         └────────┬─────────┘
                                                                  │
                                                         ┌────────▼─────────┐
                                                         │   DQ Report      │
                                                         │   (API + DB)     │
                                                         └──────────────────┘
```

### Services

1. **Validator Service**: Consumes raw data, validates against schemas and business rules, routes to valid/invalid topics
2. **DQ Report Service**: Consumes violations, stores in SQLite, exposes REST API for querying

### Key Features

- ✅ **At-Least-Once Delivery**: Manual offset commits ensure no data loss
- ✅ **Idempotent Processing**: Duplicate violations are handled gracefully
- ✅ **Schema Validation**: JSON Schema validation with format checking
- ✅ **Business Rule Validation**: Flexible YAML-based business rules
- ✅ **Dead Letter Queue**: Invalid messages routed to DLQ topics
- ✅ **Structured Logging**: JSON-formatted logs for observability
- ✅ **REST API**: Query violations and generate reports
- ✅ **Fully Containerized**: Single `docker-compose up` command to run

### 🎁 Bonus Features

- ✅ **Schema Registry**: Confluent Schema Registry for centralized schema management
- ✅ **Interactive Dashboard**: Real-time DQ visualization with Chart.js
- ✅ **DLQ Replay**: Automated replay mechanism for reprocessing failed messages

> See [BONUS_FEATURES.md](BONUS_FEATURES.md) for detailed documentation on bonus features.

## Technology Stack

- **Language**: Python 3.11
- **Message Broker**: Apache Kafka
- **Web Framework**: FastAPI + Uvicorn
- **Data Validation**: jsonschema, PyYAML
- **Database**: SQLite
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest, requests
- **Logging**: python-json-logger

## Project Structure

```
dq-pipeline/
├── docker-compose.yml          # Docker Compose configuration
├── .gitignore                  # Git ignore patterns
├── README.md                   # This file
├── DESIGN.md                   # Architecture and design decisions
├── contracts/                  # JSON Schema contracts
│   ├── customers/
│   │   └── v1.json
│   ├── orders/
│   │   └── v1.json
│   └── lines/
│       └── v1.json
├── rules/                      # Business rules
│   └── business_rules.yml
├── services/
│   ├── validator/              # Validator service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── __main__.py
│   │       ├── validation.py
│   │       └── kafka_client.py
│   └── dq_report/              # DQ Report service
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── __main__.py
│           ├── database.py
│           └── consumer.py
└── tests/                      # Test suite
    ├── test_integration.py
    └── test_unit_validation.py
```

## Setup and Run Instructions

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available for Docker

### Quick Start

1. **Clone or navigate to the project directory**:
   ```bash
   cd dq-pipeline
   ```

2. **Start all services**:
   ```bash
   docker-compose up --build
   ```

   This will:
   - Start Zookeeper and Kafka
   - Create all required Kafka topics
   - Start the Validator service
   - Start the DQ Report service with API on port 8000

3. **Wait for services to be ready** (approximately 30-60 seconds)

4. **Verify services are running**:
   ```bash
   curl http://localhost:8000/health
   ```

### Stopping Services

```bash
docker-compose down
```

To remove volumes (database data):
```bash
docker-compose down -v
```

## Kafka Topics

The pipeline uses the following Kafka topics:

### Input Topics (Raw Data)
- `raw.customers` - Raw customer data
- `raw.orders` - Raw order data
- `raw.lines` - Raw order line items

### Output Topics (Valid Data)
- `valid.customers` - Validated customer data
- `valid.orders` - Validated order data
- `valid.lines` - Validated line items

### Dead Letter Queue Topics
- `invalid.customers.dlq` - Invalid customer records
- `invalid.orders.dlq` - Invalid order records
- `invalid.lines.dlq` - Invalid line items

### Violations Topic
- `dq.violations` - Data quality violation events

## Web Dashboard

Access the interactive DQ Dashboard at:
```
http://localhost:8000/
```

The dashboard provides:
- Real-time violation statistics
- Interactive charts (pie chart and bar chart)
- Top violations table with severity indicators
- Auto-refresh every 30 seconds

## API Endpoints

The DQ Report service exposes the following REST API endpoints on port 8000:

### Dashboard

```bash
# Access interactive dashboard
open http://localhost:8000/
```

### Health Check

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "consumer": "running",
  "total_violations": 42
}
```

### Get DQ Report

Get aggregated violation counts grouped by domain, rule, and hour.

```bash
curl http://localhost:8000/dq-report
```

**Response**:
```json
{
  "total_records": 10,
  "violations": [
    {
      "domain": "customers",
      "rule_name": "age_minimum_requirement",
      "hour_bucket": "2024-01-20-14",
      "violation_count": 5
    }
  ]
}
```

### Get Top Violations

Get the top N most frequent violations in the last X hours.

```bash
curl "http://localhost:8000/dq-top-violations?hours=24&limit=5"
```

**Parameters**:
- `hours` (optional): Number of hours to look back (default: 24, max: 168)
- `limit` (optional): Maximum results to return (default: 5, max: 50)

**Response**:
```json
{
  "hours": 24,
  "limit": 5,
  "total_records": 3,
  "top_violations": [
    {
      "domain": "orders",
      "rule_name": "minimum_order_value",
      "violation_count": 15,
      "first_seen": "2024-01-20T10:00:00Z",
      "last_seen": "2024-01-20T14:30:00Z"
    }
  ]
}
```

### Get Sample Violations

Get a sample of raw violation records for a specific domain.

```bash
curl "http://localhost:8000/dq-sample?domain=customers&limit=10"
```

**Parameters**:
- `domain` (required): Domain name (e.g., 'customers', 'orders', 'lines')
- `limit` (optional): Maximum records to return (default: 10, max: 100)

**Response**:
```json
{
  "domain": "customers",
  "limit": 10,
  "total_records": 3,
  "violations": [
    {
      "message_id": "customers-0-123",
      "timestamp": "2024-01-20T14:30:00Z",
      "domain": "customers",
      "field": "age",
      "rule_name": "age_minimum_requirement",
      "violation_type": "business_rule_error",
      "message": "Customer age must be 18 or older",
      "value": "16"
    }
  ]
}
```

### Get Statistics

Get overall database statistics.

```bash
curl http://localhost:8000/dq-stats
```

**Response**:
```json
{
  "statistics": {
    "total_violations": 42,
    "violations_by_domain": {
      "customers": 15,
      "orders": 20,
      "lines": 7
    },
    "latest_violation": "2024-01-20T14:30:00Z"
  }
}
```

### DLQ Management (Bonus Feature)

#### List DLQ Topics

Get information about all DLQ topics and message counts:

```bash
curl http://localhost:8000/dlq/list
```

**Response**:
```json
{
  "dlq_topics": [
    {
      "topic": "invalid.customers.dlq",
      "domain": "customers",
      "message_count": 15,
      "target_topic": "raw.customers"
    }
  ],
  "total_dlq_messages": 26
}
```

#### Replay DLQ Messages

Replay messages from a domain's DLQ back to its raw topic:

```bash
# Replay all messages
curl -X POST "http://localhost:8000/dlq/replay/customers"

# Replay limited messages
curl -X POST "http://localhost:8000/dlq/replay/customers?max_messages=10"
```

**Response**:
```json
{
  "dlq_topic": "invalid.customers.dlq",
  "target_topic": "raw.customers",
  "messages_read": 15,
  "messages_replayed": 15,
  "errors": 0,
  "error_details": []
}
```

### Schema Registry (Bonus Feature)

Access Confluent Schema Registry at `http://localhost:8081`:

```bash
# List all schemas
curl http://localhost:8081/subjects

# Get specific schema
curl http://localhost:8081/subjects/customers-value/versions/latest
```

## Testing

### Unit Tests

Run unit tests for validation logic:

```bash
# Install pytest
pip install pytest

# Run unit tests
cd dq-pipeline
python -m pytest tests/test_unit_validation.py -v
```

### Integration Tests

Run end-to-end integration tests:

```bash
# Ensure services are running
docker-compose up -d

# Install dependencies
pip install kafka-python requests

# Run integration tests
python tests/test_integration.py
```

The integration tests will:
1. Produce valid and invalid messages to raw topics
2. Verify messages are routed correctly
3. Check violations are recorded in the database
4. Test all API endpoints

## Producing Test Messages

You can produce test messages using the Kafka console producer or Python:

### Using Python

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Valid customer
customer = {
    "id": "CUST-123456",
    "name": "John Doe",
    "email": "john.doe@example.com",
    "age": 30,
    "signup_date": "2024-01-20",
    "status": "active"
}

producer.send('raw.customers', value=customer)
producer.flush()
```

### Using Kafka Console Producer

```bash
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic raw.customers

# Then paste JSON:
{"id":"CUST-123456","name":"John Doe","email":"john.doe@example.com","age":30,"signup_date":"2024-01-20"}
```

## Monitoring and Logs

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f validator
docker-compose logs -f dq_report
```

### View Kafka Topics

```bash
# List topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# Consume from a topic
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic valid.customers \
  --from-beginning
```

## Configuration

### Environment Variables

Services can be configured via environment variables in `docker-compose.yml`:

- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address (default: `kafka:29092`)
- `LOG_LEVEL`: Logging level (default: `INFO`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Adding New Domains

1. **Create JSON Schema**: Add schema file to `contracts/{domain}/v1.json`
2. **Add Business Rules**: Add rules to `rules/business_rules.yml`
3. **Create Topics**: Add topics to `docker-compose.yml` kafka-setup service
4. **Update Validator**: Add domain to raw topics list in validator service

## Troubleshooting

### Services won't start

- Ensure Docker has enough memory (4GB minimum)
- Check if ports 8000 and 9092 are available
- View logs: `docker-compose logs`

### Messages not being processed

- Check validator logs: `docker-compose logs validator`
- Verify topics exist: `docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092`
- Check Kafka health: `docker-compose ps`

### API returns empty results

- Wait a few seconds for messages to be processed
- Check if messages were produced: `docker-compose logs validator`
- Verify consumer is running: `curl http://localhost:8000/health`

## Performance Considerations

- **Throughput**: Current configuration handles ~1000 messages/second per partition
- **Latency**: End-to-end latency typically <100ms
- **Scalability**: Can scale validator service horizontally (increase consumer group members)
- **Database**: SQLite suitable for development; use PostgreSQL/MySQL for production

## Security Considerations

- **Authentication**: Add Kafka SASL/SSL for production
- **API Security**: Add authentication/authorization to FastAPI endpoints
- **Network**: Use Docker networks to isolate services
- **Secrets**: Use Docker secrets or environment variables for sensitive data

## License

This project is provided as-is for educational and development purposes.

## Support

For issues or questions, please check:
- Service logs: `docker-compose logs`
- Health endpoint: `http://localhost:8000/health`
- DESIGN.md for architectural details
