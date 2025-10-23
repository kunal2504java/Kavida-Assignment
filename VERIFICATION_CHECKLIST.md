# DQ Pipeline Verification Checklist

Use this checklist to verify that the Data Quality Pipeline is working correctly.

## ✅ Pre-Flight Checks

### Docker Environment
- [ ] Docker is installed and running
- [ ] Docker Compose is installed
- [ ] At least 4GB RAM available for Docker
- [ ] Ports 8000 and 9092 are available

```bash
# Check Docker
docker --version
docker-compose --version
docker info | grep "Total Memory"

# Check ports
netstat -an | findstr "8000"
netstat -an | findstr "9092"
```

## ✅ Service Startup

### 1. Start Services
```bash
cd dq-pipeline
docker-compose up --build
```

- [ ] Zookeeper starts successfully
- [ ] Kafka starts successfully
- [ ] kafka-setup creates all topics
- [ ] Validator service starts
- [ ] DQ Report service starts

### 2. Verify Containers
```bash
docker-compose ps
```

Expected output: All services should be "Up"
- [ ] zookeeper (Up)
- [ ] kafka (Up)
- [ ] validator (Up)
- [ ] dq_report (Up)

### 3. Check Logs
```bash
docker-compose logs | grep -i error
```

- [ ] No critical errors in logs
- [ ] Validator shows "ready, waiting for messages"
- [ ] DQ Report shows "started"

## ✅ Kafka Topics

### Verify Topics Created
```bash
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

Expected topics:
- [ ] raw.customers
- [ ] raw.orders
- [ ] raw.lines
- [ ] valid.customers
- [ ] valid.orders
- [ ] valid.lines
- [ ] invalid.customers.dlq
- [ ] invalid.orders.dlq
- [ ] invalid.lines.dlq
- [ ] dq.violations

## ✅ API Health

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
- [ ] Status: "healthy"
- [ ] Database: "connected"
- [ ] Consumer: "running"

### API Documentation
```bash
# Open in browser
start http://localhost:8000/docs
```

- [ ] Swagger UI loads
- [ ] All endpoints visible
- [ ] Can execute test requests

## ✅ Data Flow Testing

### 1. Produce Valid Customer
```bash
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic raw.customers
```

Paste and press Enter:
```json
{"id":"CUST-999001","name":"Test User","email":"test@example.com","age":30,"signup_date":"2024-01-20","status":"active"}
```

- [ ] Message sent successfully
- [ ] Validator logs show "Processing message"
- [ ] Validator logs show "VALIDATED"

### 2. Verify Valid Message Routing
```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic valid.customers \
  --from-beginning \
  --max-messages 1
```

- [ ] Valid customer appears in valid.customers topic

### 3. Produce Invalid Customer
```bash
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic raw.customers
```

Paste and press Enter:
```json
{"id":"CUST-999002","name":"Underage User","email":"test@example.com","age":16,"signup_date":"2024-01-20"}
```

- [ ] Message sent successfully
- [ ] Validator logs show "VALIDATION_FAILED"

### 4. Verify Invalid Message Routing
```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic invalid.customers.dlq \
  --from-beginning \
  --max-messages 1
```

- [ ] Invalid customer appears in DLQ topic

### 5. Verify Violation Event
```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dq.violations \
  --from-beginning \
  --max-messages 1
```

- [ ] Violation event appears in dq.violations topic
- [ ] Contains message_id, domain, field, rule_name

## ✅ API Endpoints

### 1. DQ Report
```bash
curl http://localhost:8000/dq-report
```

- [ ] Returns JSON response
- [ ] Contains "total_records" field
- [ ] Contains "violations" array

### 2. Top Violations
```bash
curl "http://localhost:8000/dq-top-violations?hours=24&limit=5"
```

- [ ] Returns JSON response
- [ ] Contains "top_violations" array
- [ ] Shows violation counts

### 3. Sample Violations
```bash
curl "http://localhost:8000/dq-sample?domain=customers&limit=10"
```

- [ ] Returns JSON response
- [ ] Contains "violations" array
- [ ] Shows customer violations (if any sent)

### 4. Statistics
```bash
curl http://localhost:8000/dq-stats
```

- [ ] Returns JSON response
- [ ] Contains "total_violations"
- [ ] Contains "violations_by_domain"

## ✅ Unit Tests

### Run Unit Tests
```bash
pip install -r requirements-test.txt
pytest tests/test_unit_validation.py -v
```

- [ ] All schema validation tests pass
- [ ] All business rule tests pass
- [ ] All combined validation tests pass
- [ ] No test failures

## ✅ Integration Tests

### Run Integration Tests
```bash
pip install kafka-python requests
python tests/test_integration.py
```

- [ ] Health check test passes
- [ ] Valid customer flow test passes
- [ ] Invalid customer flow test passes
- [ ] Invalid order flow test passes
- [ ] API report test passes
- [ ] API top violations test passes

## ✅ Sample Data Script

### Run Sample Data Producer
```bash
pip install kafka-python
python produce_sample_data.py
```

- [ ] Script runs without errors
- [ ] Valid customer sent
- [ ] Invalid customer sent
- [ ] Valid order sent
- [ ] Invalid order sent

### Verify Results
```bash
# Wait 5 seconds for processing
sleep 5

# Check violations
curl http://localhost:8000/dq-report
```

- [ ] Violations appear in report
- [ ] Both customer and order violations present

## ✅ Performance & Monitoring

### Check Service Resources
```bash
docker stats --no-stream
```

- [ ] Validator CPU < 50%
- [ ] DQ Report CPU < 50%
- [ ] Kafka memory < 2GB
- [ ] No container restarts

### Check Logs for Errors
```bash
docker-compose logs validator | grep -i error
docker-compose logs dq_report | grep -i error
```

- [ ] No unexpected errors
- [ ] No connection failures
- [ ] No timeout errors

## ✅ Cleanup & Restart

### Stop Services
```bash
docker-compose down
```

- [ ] All containers stopped
- [ ] No errors during shutdown

### Restart Services
```bash
docker-compose up -d
```

- [ ] All services restart successfully
- [ ] Health check passes after restart
- [ ] Previous data persists (if volume not removed)

### Full Cleanup
```bash
docker-compose down -v
```

- [ ] All containers removed
- [ ] All volumes removed
- [ ] Clean slate for next run

## 📊 Success Criteria

All checks should pass for a successful verification:

- ✅ All services start without errors
- ✅ All Kafka topics created
- ✅ API health check returns healthy
- ✅ Valid messages routed to valid topics
- ✅ Invalid messages routed to DLQ
- ✅ Violations recorded in database
- ✅ All API endpoints return data
- ✅ Unit tests pass
- ✅ Integration tests pass

## 🐛 Troubleshooting

### Services won't start
```bash
# Check Docker logs
docker-compose logs

# Restart Docker Desktop
# Then try again
docker-compose down -v
docker-compose up --build
```

### Kafka connection errors
```bash
# Wait longer for Kafka to be ready
# Kafka can take 30-60 seconds to fully start

# Check Kafka health
docker exec -it kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

### API not responding
```bash
# Check if port is in use
netstat -an | findstr "8000"

# Check DQ Report logs
docker-compose logs dq_report

# Restart just the API service
docker-compose restart dq_report
```

### No violations showing
```bash
# Check if messages were produced
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic raw.customers \
  --from-beginning

# Check validator is processing
docker-compose logs validator | grep "Processing"

# Check consumer is running
curl http://localhost:8000/health
```

## 📝 Notes

- First startup may take longer (downloading images)
- Kafka needs 30-60 seconds to be fully ready
- Wait 5-10 seconds after sending messages before checking results
- Use `docker-compose logs -f` to watch real-time logs

---

**If all checks pass, your DQ Pipeline is working correctly! 🎉**
