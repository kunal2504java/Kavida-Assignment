# Bonus Features Documentation

This document describes the optional bonus features implemented in the Data Quality Pipeline.

## 🎯 Overview

The following bonus features have been added to enhance the DQ pipeline:

1. **Schema Registry Integration** - Confluent Schema Registry for centralized schema management
2. **DQ Dashboard** - Interactive web dashboard with real-time visualizations
3. **DLQ Replay Mechanism** - Automated replay of messages from Dead Letter Queues

---

## 1. Schema Registry Integration

### What is it?

Confluent Schema Registry provides centralized schema management and versioning for Kafka topics. It ensures schema compatibility and evolution across producers and consumers.

### How to Access

The Schema Registry is available at:
- **URL**: `http://localhost:8081`
- **Container**: `schema-registry`

### API Endpoints

```bash
# List all subjects (schemas)
curl http://localhost:8081/subjects

# Get schema for a subject
curl http://localhost:8081/subjects/customers-value/versions/latest

# Register a new schema
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "{\"type\":\"record\",\"name\":\"Customer\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}"}' \
  http://localhost:8081/subjects/customers-value/versions
```

### Configuration

The Schema Registry is configured in `docker-compose.yml`:

```yaml
schema-registry:
  image: confluentinc/cp-schema-registry:7.5.0
  ports:
    - "8081:8081"
  environment:
    SCHEMA_REGISTRY_HOST_NAME: schema-registry
    SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'kafka:29092'
```

### Integration with Validator

The validator service has access to the Schema Registry via the `SCHEMA_REGISTRY_URL` environment variable:

```yaml
validator:
  environment:
    SCHEMA_REGISTRY_URL: http://schema-registry:8081
```

### Benefits

- ✅ **Centralized Schema Management** - Single source of truth for schemas
- ✅ **Schema Versioning** - Track schema evolution over time
- ✅ **Compatibility Checking** - Prevent breaking changes
- ✅ **Schema Discovery** - Easy to find and browse schemas

---

## 2. DQ Dashboard

### What is it?

An interactive web dashboard that provides real-time visualization of data quality violations with charts and statistics.

### How to Access

Open your browser and navigate to:
```
http://localhost:8000/
```

The dashboard will automatically load and display:
- Total violations count
- Violations by domain (customers, orders, lines)
- Interactive charts (pie chart and bar chart)
- Top violations table
- Auto-refresh every 30 seconds

### Features

#### 📊 **Statistics Cards**
- Total violations across all domains
- Individual counts for customers, orders, and lines
- Hover effects for better UX

#### 📈 **Visualizations**
1. **Pie Chart** - Violations by domain
   - Shows distribution across customers, orders, and lines
   - Interactive tooltips

2. **Bar Chart** - Top 10 violation rules
   - Displays most frequent validation failures
   - Sortable by count

#### 📋 **Top Violations Table**
- Domain name
- Rule name
- Violation count
- Severity badge (High/Medium/Low)
- First and last seen timestamps

#### 🔄 **Auto-Refresh**
- Refreshes data every 30 seconds
- Manual refresh button available
- Loading indicators

### Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript
- **Charts**: Chart.js 4.4.0
- **Styling**: Custom CSS with gradient backgrounds
- **Backend**: FastAPI serving static files

### API Integration

The dashboard consumes the following APIs:
- `GET /dq-stats` - Overall statistics
- `GET /dq-top-violations` - Top violations data

### Customization

To customize the dashboard, edit:
```
services/dq_report/app/static/dashboard.html
```

You can modify:
- Colors and styling (CSS section)
- Chart types and configurations
- Refresh interval
- Number of top violations displayed

---

## 3. DLQ Replay Mechanism

### What is it?

Automated system to replay messages from Dead Letter Queue (DLQ) topics back to raw topics for reprocessing. This is useful when:
- Validation rules have been fixed
- Schema issues have been resolved
- Temporary failures need to be retried

### API Endpoints

#### List DLQ Topics

Get information about all DLQ topics and their message counts:

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
    },
    {
      "topic": "invalid.orders.dlq",
      "domain": "orders",
      "message_count": 8,
      "target_topic": "raw.orders"
    },
    {
      "topic": "invalid.lines.dlq",
      "domain": "lines",
      "message_count": 3,
      "target_topic": "raw.lines"
    }
  ],
  "total_dlq_messages": 26
}
```

#### Replay Domain DLQ

Replay all messages from a domain's DLQ back to its raw topic:

```bash
# Replay all customers DLQ messages
curl -X POST "http://localhost:8000/dlq/replay/customers"

# Replay only first 10 messages
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

#### Custom DLQ Replay

Replay messages from any DLQ topic to any target topic:

```bash
curl -X POST "http://localhost:8000/dlq/replay-custom?dlq_topic=invalid.customers.dlq&target_topic=raw.customers&max_messages=5"
```

### Use Cases

#### 1. **Fix and Replay**

When you've fixed a validation rule or schema:

```bash
# 1. Check DLQ message count
curl http://localhost:8000/dlq/list

# 2. Fix the validation rule in rules/business_rules.yml

# 3. Restart validator service
docker compose restart validator

# 4. Replay DLQ messages
curl -X POST "http://localhost:8000/dlq/replay/customers"
```

#### 2. **Partial Replay**

Replay only a subset of messages for testing:

```bash
# Replay first 5 messages
curl -X POST "http://localhost:8000/dlq/replay/customers?max_messages=5"

# Check if they were processed correctly
curl "http://localhost:8000/dq-sample?domain=customers&limit=10"
```

#### 3. **Batch Reprocessing**

Replay all domains at once:

```bash
# Replay customers
curl -X POST "http://localhost:8000/dlq/replay/customers"

# Replay orders
curl -X POST "http://localhost:8000/dlq/replay/orders"

# Replay lines
curl -X POST "http://localhost:8000/dlq/replay/lines"
```

### Safety Features

- ✅ **At-Least-Once Delivery** - Messages are confirmed before being considered replayed
- ✅ **Error Tracking** - Failed replays are logged with details
- ✅ **Configurable Limits** - Control how many messages to replay
- ✅ **Statistics** - Detailed stats on replay operations
- ✅ **Idempotent** - Safe to replay multiple times

### Implementation Details

The DLQ replay service is implemented in:
```
services/dq_report/app/dlq_replay.py
```

Key components:
- `DLQReplayService` - Main service class
- `replay_dlq_messages()` - Core replay logic
- `replay_domain_dlq()` - Domain-specific replay
- `get_dlq_message_count()` - Count messages in DLQ
- `list_dlq_topics()` - List all DLQ topics

---

## 🚀 Quick Start with Bonus Features

### 1. Start All Services

```bash
docker compose up --build
```

This will start:
- Zookeeper
- Kafka
- **Schema Registry** (new!)
- Validator
- DQ Report with Dashboard

### 2. Access the Dashboard

Open browser: `http://localhost:8000/`

### 3. Send Test Data

```bash
python produce_sample_data.py
```

### 4. View Violations in Dashboard

The dashboard will automatically update with:
- Violation counts
- Charts
- Top violations table

### 5. Check DLQ Messages

```bash
curl http://localhost:8000/dlq/list
```

### 6. Replay DLQ Messages

```bash
curl -X POST "http://localhost:8000/dlq/replay/customers"
```

### 7. Access Schema Registry

```bash
# List schemas
curl http://localhost:8081/subjects

# Check Schema Registry health
curl http://localhost:8081/
```

---

## 📊 Updated API Endpoints

With bonus features, the complete API now includes:

### Core Endpoints
- `GET /` - **DQ Dashboard** (new!)
- `GET /api` - API information
- `GET /health` - Health check
- `GET /dq-report` - Aggregated violations
- `GET /dq-top-violations` - Top violations
- `GET /dq-sample` - Sample violations
- `GET /dq-stats` - Statistics

### DLQ Replay Endpoints (new!)
- `GET /dlq/list` - List DLQ topics
- `POST /dlq/replay/{domain}` - Replay domain DLQ
- `POST /dlq/replay-custom` - Custom DLQ replay

### Swagger Documentation

Access interactive API docs at:
```
http://localhost:8000/docs
```

---

## 🎓 Benefits Summary

### Schema Registry
- ✅ Centralized schema management
- ✅ Schema versioning and evolution
- ✅ Compatibility checking
- ✅ Industry-standard solution

### DQ Dashboard
- ✅ Real-time visualization
- ✅ Interactive charts
- ✅ Auto-refresh capability
- ✅ Professional UI/UX
- ✅ No additional dependencies

### DLQ Replay
- ✅ Automated reprocessing
- ✅ Configurable replay limits
- ✅ Detailed statistics
- ✅ Safe and idempotent
- ✅ RESTful API

---

## 🔧 Configuration

### Schema Registry

Edit `docker-compose.yml`:
```yaml
schema-registry:
  environment:
    SCHEMA_REGISTRY_HOST_NAME: schema-registry
    SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'kafka:29092'
    # Add more configuration as needed
```

### Dashboard

Edit `services/dq_report/app/static/dashboard.html`:
- Modify refresh interval (default: 30 seconds)
- Change chart colors
- Adjust table columns
- Customize styling

### DLQ Replay

No configuration needed - works out of the box!

---

## 📝 Notes

- All bonus features are **production-ready**
- Features are **fully integrated** with existing functionality
- **No breaking changes** to existing APIs
- **Backward compatible** with previous version
- All features include **comprehensive error handling**

---

## 🎉 Conclusion

These bonus features significantly enhance the Data Quality Pipeline by providing:

1. **Better Schema Management** - Schema Registry
2. **Improved Visibility** - Interactive Dashboard
3. **Operational Excellence** - DLQ Replay

All features work seamlessly together and maintain the production-ready quality of the base implementation!
