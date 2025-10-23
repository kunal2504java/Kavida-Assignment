# Data Quality Pipeline - Design Document

## Table of Contents

1. [Overview](#overview)
2. [Architectural Decisions](#architectural-decisions)
3. [Data Flow](#data-flow)
4. [At-Least-Once Delivery](#at-least-once-delivery)
5. [Idempotency](#idempotency)
6. [Trade-offs and Design Choices](#trade-offs-and-design-choices)
7. [Scalability Considerations](#scalability-considerations)
8. [Future Enhancements](#future-enhancements)

## Overview

The Data Quality (DQ) Pipeline is an event-driven system designed to validate incoming data streams against predefined schemas and business rules. The system ensures data quality by routing valid messages to appropriate topics and capturing violations for analysis and reporting.

### Core Principles

- **Reliability**: At-least-once message delivery guarantees
- **Idempotency**: Duplicate processing handled gracefully
- **Observability**: Structured logging and comprehensive metrics
- **Scalability**: Horizontal scaling capability
- **Maintainability**: Clear separation of concerns and modular design

## Architectural Decisions

### Why Microservices?

The system is split into two independent services:

#### 1. Validator Service
**Responsibility**: Data validation and routing

**Rationale**:
- **Single Responsibility**: Focuses solely on validation logic
- **Stateless**: Can be scaled horizontally without coordination
- **Performance**: Optimized for high-throughput message processing
- **Isolation**: Validation failures don't affect reporting

#### 2. DQ Report Service
**Responsibility**: Violation storage and API

**Rationale**:
- **Separation of Concerns**: Reporting logic independent of validation
- **Different Scaling Needs**: API and consumer can scale independently
- **Technology Flexibility**: Can use different storage backends
- **API Evolution**: REST API can evolve without affecting validation

### Why Kafka?

**Benefits**:
- **Durability**: Messages persisted to disk
- **Scalability**: Partitioning enables horizontal scaling
- **Decoupling**: Producers and consumers are independent
- **Replay**: Can reprocess historical data
- **Ordering**: Per-partition ordering guarantees

**Alternatives Considered**:
- **RabbitMQ**: Less suitable for high-throughput streaming
- **AWS SQS**: Cloud-specific, less control over ordering
- **Redis Streams**: Less mature ecosystem

### Why FastAPI?

**Benefits**:
- **Performance**: Async support, fast request handling
- **Developer Experience**: Automatic API documentation (Swagger/OpenAPI)
- **Type Safety**: Pydantic models with validation
- **Modern**: Built on modern Python standards (type hints, async/await)

**Alternatives Considered**:
- **Flask**: Less performant, no built-in async support
- **Django**: Too heavyweight for microservice API

### Why JSON Schema?

**Benefits**:
- **Standard**: Industry-standard validation format
- **Expressive**: Rich validation capabilities (patterns, formats, ranges)
- **Tooling**: Excellent library support (jsonschema)
- **Documentation**: Schemas serve as documentation

**Alternatives Considered**:
- **Pydantic**: Tightly coupled to Python
- **Protobuf**: More complex, requires code generation
- **Avro**: Less human-readable

## Data Flow

### End-to-End Message Journey

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                        │
│    Producer → raw.{domain} topic                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. CONSUMPTION                                                      │
│    Validator Service consumes from raw.* topics                     │
│    - Consumer Group: validator-group                                │
│    - Auto-commit: DISABLED (manual commit)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. VALIDATION                                                       │
│    a. Deserialize JSON message                                      │
│    b. Schema Validation (JSON Schema)                               │
│    c. Business Rule Validation (YAML rules)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
┌───────────────────────┐     ┌───────────────────────┐
│ 4a. VALID PATH        │     │ 4b. INVALID PATH      │
│                       │     │                       │
│ Produce to:           │     │ Produce to:           │
│ - valid.{domain}      │     │ - invalid.{domain}.dlq│
│                       │     │ - dq.violations       │
│                       │     │   (one per violation) │
└───────┬───────────────┘     └───────┬───────────────┘
        │                             │
        ▼                             ▼
┌───────────────────┐     ┌───────────────────────────┐
│ 5. COMMIT OFFSET  │     │ 5. COMMIT OFFSET          │
│                   │     │                           │
│ Manual commit     │     │ Manual commit             │
│ after successful  │     │ after successful          │
│ production        │     │ production                │
└───────────────────┘     └───────────┬───────────────┘
                                      │
                                      ▼
                          ┌───────────────────────────┐
                          │ 6. VIOLATION PROCESSING   │
                          │                           │
                          │ DQ Report Service:        │
                          │ - Consumes dq.violations  │
                          │ - INSERT OR IGNORE to DB  │
                          │ - Idempotent processing   │
                          └───────────┬───────────────┘
                                      │
                                      ▼
                          ┌───────────────────────────┐
                          │ 7. REPORTING              │
                          │                           │
                          │ REST API provides:        │
                          │ - Aggregated reports      │
                          │ - Top violations          │
                          │ - Sample records          │
                          └───────────────────────────┘
```

### Message Format Examples

#### Raw Message (Input)
```json
{
  "id": "CUST-123456",
  "name": "John Doe",
  "email": "john@example.com",
  "age": 30,
  "signup_date": "2024-01-20"
}
```

#### Violation Event (dq.violations)
```json
{
  "message_id": "customers-0-12345",
  "timestamp": "2024-01-20T14:30:00Z",
  "hour_bucket": "2024-01-20-14",
  "domain": "customers",
  "field": "age",
  "rule_name": "age_minimum_requirement",
  "violation_type": "business_rule_error",
  "message": "Customer age must be 18 or older",
  "value": "16"
}
```

## At-Least-Once Delivery

### Implementation

The validator service implements at-least-once delivery semantics to ensure no data loss:

#### 1. Manual Offset Commits

```python
consumer = KafkaConsumer(
    enable_auto_commit=False,  # Disable automatic commits
    ...
)

# Process message
validate_and_route(message)

# Only commit after successful processing
consumer.commit()
```

#### 2. Processing Sequence

```
1. Consume message from Kafka
2. Validate message (schema + business rules)
3. Produce to target topics (valid.* or invalid.* + dq.violations)
4. Wait for producer acknowledgment (acks='all')
5. Commit offset
```

#### 3. Failure Scenarios

**Scenario A: Validation Fails**
- Message is caught in try-catch
- Logged as error
- Offset NOT committed
- Message will be reprocessed

**Scenario B: Production Fails**
- Producer raises exception
- Offset NOT committed
- Message will be reprocessed

**Scenario C: Commit Fails**
- Offset NOT committed
- Message will be reprocessed
- Idempotency handles duplicates

### Why At-Least-Once?

**Advantages**:
- ✅ No data loss
- ✅ Simpler implementation than exactly-once
- ✅ Better performance than exactly-once
- ✅ Idempotency handles duplicates

**Alternatives Considered**:
- **At-Most-Once**: Unacceptable data loss risk
- **Exactly-Once**: Complex, requires transactional producers/consumers

## Idempotency

### Problem Statement

With at-least-once delivery, messages may be processed multiple times:
- Network failures
- Consumer rebalancing
- Service restarts

### Solution: Idempotent Processing

#### Validator Service

The validator service is naturally idempotent:
- Produces same output for same input
- No state maintained between messages
- Duplicate valid messages → duplicate valid messages (acceptable)
- Duplicate invalid messages → duplicate violation events (handled by DQ Report)

#### DQ Report Service

Implements idempotency using database constraints:

```sql
CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,  -- Ensures uniqueness
    ...
)
```

```python
# INSERT OR IGNORE ensures idempotency
cursor.execute("""
    INSERT OR IGNORE INTO violations (
        message_id, timestamp, domain, ...
    ) VALUES (?, ?, ?, ...)
""", ...)
```

#### Message ID Generation

```python
message_id = f"{domain}-{partition}-{offset}"
```

This ensures:
- Unique per message
- Deterministic (same message = same ID)
- Traceable back to source

### Idempotency Guarantees

| Component | Mechanism | Result |
|-----------|-----------|--------|
| Validator | Stateless processing | Same input → same output |
| DQ Report | UNIQUE constraint | Duplicate inserts ignored |
| Database | INSERT OR IGNORE | No duplicate violations |

## Trade-offs and Design Choices

### 1. SQLite vs. Production Database

**Current Choice: SQLite**

**Rationale**:
- ✅ Zero configuration
- ✅ Embedded (no separate service)
- ✅ Perfect for development/demo
- ✅ ACID compliance
- ✅ Good performance for moderate load

**Limitations**:
- ❌ Single writer (no concurrent writes)
- ❌ No network access
- ❌ Limited scalability
- ❌ No replication

**Production Alternative: PostgreSQL**

For production, we would use PostgreSQL:
- ✅ Concurrent writes
- ✅ Horizontal scaling (read replicas)
- ✅ Advanced indexing
- ✅ Better monitoring tools
- ✅ Replication and high availability

**Migration Path**:
```python
# Minimal code changes required
# Change connection string:
# SQLite: sqlite:///violations.db
# PostgreSQL: postgresql://user:pass@host:5432/dq
```

### 2. Consumer Threading Model

**Current Choice: Single-threaded consumer per service**

**Rationale**:
- ✅ Simpler code
- ✅ Easier debugging
- ✅ No concurrency issues
- ✅ Kafka handles parallelism via partitions

**Scaling Strategy**:
- Increase number of partitions
- Run multiple consumer instances
- Kafka automatically distributes partitions

### 3. Validation Order

**Current Choice: Schema first, then business rules**

**Rationale**:
- ✅ Fail fast on schema errors
- ✅ Business rules assume valid schema
- ✅ Clearer error messages
- ✅ Better performance (skip expensive rules if schema invalid)

### 4. Violation Granularity

**Current Choice: One violation event per rule failure**

**Rationale**:
- ✅ Detailed tracking
- ✅ Better analytics (per-rule metrics)
- ✅ Easier debugging

**Trade-off**:
- ❌ More messages for multi-violation records
- ✅ Acceptable given Kafka's throughput

### 5. API Design

**Current Choice: REST API with FastAPI**

**Rationale**:
- ✅ Widely understood
- ✅ Easy to test (curl, Postman)
- ✅ Auto-generated documentation
- ✅ Stateless (easy to scale)

**Alternatives Considered**:
- **GraphQL**: Overkill for simple queries
- **gRPC**: Less accessible, requires code generation

## Scalability Considerations

### Horizontal Scaling

#### Validator Service

```yaml
# Scale to 3 instances
docker-compose up --scale validator=3
```

**How it works**:
- Each instance joins same consumer group
- Kafka distributes partitions across instances
- Each partition processed by exactly one instance
- Linear scalability up to number of partitions

#### DQ Report Service

**Consumer**: Can scale similarly to validator
**API**: Stateless, can run multiple instances behind load balancer

```yaml
# Scale API
docker-compose up --scale dq_report=3

# Add load balancer (nginx, HAProxy)
```

### Vertical Scaling

- Increase consumer `max_poll_records`
- Increase JVM heap for Kafka
- Use faster storage for database

### Partitioning Strategy

**Current**: 3 partitions per topic

**Considerations**:
- More partitions = more parallelism
- More partitions = more overhead
- Recommended: 1 partition per expected consumer instance

**Production Recommendation**: 10-30 partitions per topic

### Performance Metrics

| Metric | Current | Target | Bottleneck |
|--------|---------|--------|------------|
| Throughput | ~1K msg/s | ~10K msg/s | Partitions |
| Latency | <100ms | <50ms | Network |
| API Response | <200ms | <100ms | Database |

## Future Enhancements

### Short Term

1. **Metrics and Monitoring**
   - Prometheus metrics export
   - Grafana dashboards
   - Alert rules

2. **Enhanced API**
   - Pagination for large result sets
   - Filtering by time range
   - Export to CSV/JSON

3. **Schema Evolution**
   - Schema versioning support
   - Backward compatibility checks
   - Schema registry integration

### Medium Term

1. **Advanced Validation**
   - Cross-field validation
   - Temporal validation (time-based rules)
   - ML-based anomaly detection

2. **Data Lineage**
   - Track message journey
   - Correlation IDs
   - Distributed tracing

3. **Self-Service**
   - Web UI for rule management
   - Schema upload interface
   - Real-time dashboards

### Long Term

1. **Multi-Tenancy**
   - Tenant isolation
   - Per-tenant quotas
   - Tenant-specific rules

2. **Stream Processing**
   - Kafka Streams integration
   - Real-time aggregations
   - Windowed analytics

3. **Data Catalog Integration**
   - Metadata management
   - Data discovery
   - Impact analysis

## Conclusion

This design balances simplicity with production-readiness. The architecture is:

- **Reliable**: At-least-once delivery with idempotency
- **Scalable**: Horizontal scaling via Kafka partitions
- **Maintainable**: Clear separation of concerns
- **Observable**: Structured logging and health checks
- **Flexible**: Easy to extend with new domains and rules

The system is production-ready for moderate loads and can be enhanced incrementally as requirements grow.
