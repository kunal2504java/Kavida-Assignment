"""
Main entry point for the validator service.
Consumes messages from raw topics, validates them, and routes to appropriate topics.
"""
import os
import sys
import json
import logging
from datetime import datetime
from pythonjsonlogger import jsonlogger

from .validation import DataValidator
from .kafka_client import (
    KafkaClient,
    extract_domain_from_topic,
    get_valid_topic,
    get_invalid_topic,
    get_violations_topic
)


def setup_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logging.getLogger(__name__)


def create_violation_event(message_id: str, domain: str, violation: dict) -> dict:
    """
    Create a violation event for the dq.violations topic.
    
    Args:
        message_id: Unique identifier for the message
        domain: Domain name
        violation: Violation details
        
    Returns:
        Violation event dictionary
    """
    return {
        "message_id": message_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hour_bucket": datetime.utcnow().strftime("%Y-%m-%d-%H"),
        "domain": domain,
        "field": violation.get("field", "unknown"),
        "rule_name": violation.get("rule_name", "unknown"),
        "violation_type": violation.get("type", "unknown"),
        "message": violation.get("message", ""),
        "value": str(violation.get("value", ""))
    }


def process_message(validator: DataValidator, kafka_client: KafkaClient, 
                   message, logger: logging.Logger):
    """
    Process a single message: validate and route to appropriate topics.
    
    Args:
        validator: DataValidator instance
        kafka_client: KafkaClient instance
        message: Kafka message
        logger: Logger instance
    """
    topic = message.topic
    partition = message.partition
    offset = message.offset
    
    try:
        # Deserialize message
        data = message.value
        message_key = message.key
        
        # Extract domain from topic
        domain = extract_domain_from_topic(topic)
        
        # Generate message ID for tracking
        message_id = f"{domain}-{partition}-{offset}"
        
        logger.info(
            "Processing message",
            extra={
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "domain": domain,
                "message_id": message_id
            }
        )
        
        # Validate the message
        validation_result = validator.validate(domain, data)
        
        if validation_result.is_valid:
            # Route to valid topic
            valid_topic = get_valid_topic(domain)
            kafka_client.produce_message(valid_topic, data, key=message_key)
            
            logger.info(
                "Message validated successfully",
                extra={
                    "status": "VALIDATED",
                    "topic": topic,
                    "partition": partition,
                    "offset": offset,
                    "domain": domain,
                    "message_id": message_id,
                    "routed_to": valid_topic
                }
            )
        else:
            # Route to invalid topic (DLQ)
            invalid_topic = get_invalid_topic(domain)
            kafka_client.produce_message(invalid_topic, data, key=message_key)
            
            # Create and send violation events
            violations_topic = get_violations_topic()
            for violation in validation_result.violations:
                violation_event = create_violation_event(message_id, domain, violation)
                kafka_client.produce_message(violations_topic, violation_event, key=message_id)
            
            logger.warning(
                "Message validation failed",
                extra={
                    "status": "VALIDATION_FAILED",
                    "topic": topic,
                    "partition": partition,
                    "offset": offset,
                    "domain": domain,
                    "message_id": message_id,
                    "routed_to": invalid_topic,
                    "violations_count": len(validation_result.violations),
                    "violations": [
                        {
                            "field": v.get("field"),
                            "rule": v.get("rule_name"),
                            "type": v.get("type")
                        }
                        for v in validation_result.violations
                    ]
                }
            )
        
        # Commit offset after successful processing
        kafka_client.commit_offsets()
        
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to deserialize message",
            extra={
                "status": "DESERIALIZATION_ERROR",
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "error": str(e)
            }
        )
        # Commit offset to skip malformed message
        kafka_client.commit_offsets()
        
    except Exception as e:
        logger.error(
            "Error processing message",
            extra={
                "status": "PROCESSING_ERROR",
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        # Don't commit offset - message will be reprocessed


def main():
    """Main function to run the validator service."""
    logger = setup_logging()
    logger.info("Starting validator service")
    
    # Get configuration from environment
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
    raw_topics = ['raw.customers', 'raw.orders', 'raw.lines']
    
    logger.info(
        "Service configuration",
        extra={
            "bootstrap_servers": bootstrap_servers,
            "topics": raw_topics,
            "consumer_group": "validator-group"
        }
    )
    
    # Initialize validator
    validator = DataValidator(
        contracts_path="/contracts",
        rules_path="/rules/business_rules.yml"
    )
    
    # Initialize Kafka client
    kafka_client = KafkaClient(
        bootstrap_servers=bootstrap_servers,
        consumer_group='validator-group'
    )
    
    try:
        # Create consumer and producer
        consumer = kafka_client.create_consumer(raw_topics)
        producer = kafka_client.create_producer()
        
        logger.info("Validator service ready, waiting for messages...")
        
        # Main processing loop
        for message in consumer:
            process_message(validator, kafka_client, message, logger)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error in validator service: {e}", exc_info=True)
        sys.exit(1)
    finally:
        kafka_client.close()
        logger.info("Validator service stopped")


if __name__ == "__main__":
    main()
