"""
Kafka client for consuming and producing messages.
"""
import json
import logging
from typing import Dict, Any, List
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaClient:
    """Kafka client for consuming from raw topics and producing to valid/invalid topics."""
    
    def __init__(self, bootstrap_servers: str, consumer_group: str = 'validator-group'):
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group
        self.consumer: KafkaConsumer = None
        self.producer: KafkaProducer = None
        
    def create_consumer(self, topics: List[str]) -> KafkaConsumer:
        """
        Create a Kafka consumer with at-least-once semantics.
        
        Args:
            topics: List of topics to subscribe to
            
        Returns:
            KafkaConsumer instance
        """
        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                enable_auto_commit=False,  # Manual commit for at-least-once
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None,
                max_poll_records=10,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            logger.info(f"Created consumer for topics: {topics}")
            return self.consumer
        except Exception as e:
            logger.error(f"Failed to create consumer: {e}")
            raise
    
    def create_producer(self) -> KafkaProducer:
        """
        Create a Kafka producer.
        
        Returns:
            KafkaProducer instance
        """
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1  # Ensure ordering
            )
            logger.info("Created Kafka producer")
            return self.producer
        except Exception as e:
            logger.error(f"Failed to create producer: {e}")
            raise
    
    def produce_message(self, topic: str, value: Dict[str, Any], key: str = None):
        """
        Produce a message to a Kafka topic.
        
        Args:
            topic: Target topic
            value: Message value (will be JSON serialized)
            key: Optional message key
        """
        try:
            future = self.producer.send(topic, value=value, key=key)
            # Wait for message to be sent
            record_metadata = future.get(timeout=10)
            logger.debug(
                f"Produced message to {topic} "
                f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
            )
        except KafkaError as e:
            logger.error(f"Failed to produce message to {topic}: {e}")
            raise
    
    def commit_offsets(self):
        """Manually commit consumer offsets."""
        try:
            self.consumer.commit()
            logger.debug("Committed offsets")
        except Exception as e:
            logger.error(f"Failed to commit offsets: {e}")
            raise
    
    def close(self):
        """Close consumer and producer connections."""
        if self.consumer:
            self.consumer.close()
            logger.info("Closed consumer")
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Closed producer")


def extract_domain_from_topic(topic: str) -> str:
    """
    Extract domain name from topic.
    
    Args:
        topic: Topic name (e.g., 'raw.customers')
        
    Returns:
        Domain name (e.g., 'customers')
    """
    parts = topic.split('.')
    if len(parts) >= 2:
        return parts[1]
    return topic


def get_valid_topic(domain: str) -> str:
    """Get the valid topic name for a domain."""
    return f"valid.{domain}"


def get_invalid_topic(domain: str) -> str:
    """Get the invalid/DLQ topic name for a domain."""
    return f"invalid.{domain}.dlq"


def get_violations_topic() -> str:
    """Get the violations topic name."""
    return "dq.violations"
