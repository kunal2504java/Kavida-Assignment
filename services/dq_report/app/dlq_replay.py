"""
DLQ Replay Module
Provides functionality to replay messages from Dead Letter Queue topics back to raw topics.
"""
import json
import logging
from typing import List, Dict, Optional
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError


logger = logging.getLogger(__name__)


class DLQReplayService:
    """Service for replaying messages from DLQ topics back to raw topics."""
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize DLQ Replay Service.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        
    def _get_producer(self) -> KafkaProducer:
        """Get or create Kafka producer."""
        if not self.producer:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3
            )
        return self.producer
    
    def replay_dlq_messages(
        self,
        dlq_topic: str,
        target_topic: str,
        max_messages: Optional[int] = None,
        from_beginning: bool = True
    ) -> Dict[str, any]:
        """
        Replay messages from a DLQ topic to a target topic.
        
        Args:
            dlq_topic: Source DLQ topic name
            target_topic: Target topic to replay messages to
            max_messages: Maximum number of messages to replay (None = all)
            from_beginning: Whether to start from beginning of DLQ topic
            
        Returns:
            Dictionary with replay statistics
        """
        logger.info(f"Starting DLQ replay from {dlq_topic} to {target_topic}")
        
        stats = {
            "dlq_topic": dlq_topic,
            "target_topic": target_topic,
            "messages_read": 0,
            "messages_replayed": 0,
            "errors": 0,
            "error_details": []
        }
        
        consumer = None
        producer = None
        
        try:
            # Create consumer for DLQ topic
            consumer = KafkaConsumer(
                dlq_topic,
                bootstrap_servers=self.bootstrap_servers,
                auto_offset_reset='earliest' if from_beginning else 'latest',
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=5000  # Stop after 5 seconds of no messages
            )
            
            # Get producer
            producer = self._get_producer()
            
            # Replay messages
            for message in consumer:
                stats["messages_read"] += 1
                
                try:
                    # Extract original message data
                    value = message.value
                    key = message.key.decode('utf-8') if message.key else None
                    
                    # Send to target topic
                    future = producer.send(
                        target_topic,
                        key=key,
                        value=value
                    )
                    
                    # Wait for confirmation
                    future.get(timeout=10)
                    
                    stats["messages_replayed"] += 1
                    
                    logger.debug(f"Replayed message {key} from {dlq_topic} to {target_topic}")
                    
                    # Check if we've hit the max messages limit
                    if max_messages and stats["messages_replayed"] >= max_messages:
                        logger.info(f"Reached max messages limit: {max_messages}")
                        break
                        
                except Exception as e:
                    stats["errors"] += 1
                    error_msg = f"Error replaying message: {str(e)}"
                    stats["error_details"].append(error_msg)
                    logger.error(error_msg)
            
            # Flush producer
            if producer:
                producer.flush()
            
            logger.info(f"DLQ replay completed: {stats['messages_replayed']}/{stats['messages_read']} messages replayed")
            
        except Exception as e:
            error_msg = f"Fatal error during DLQ replay: {str(e)}"
            logger.error(error_msg)
            stats["error_details"].append(error_msg)
            
        finally:
            if consumer:
                consumer.close()
        
        return stats
    
    def replay_domain_dlq(
        self,
        domain: str,
        max_messages: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Replay messages for a specific domain from its DLQ back to raw topic.
        
        Args:
            domain: Domain name (e.g., 'customers', 'orders', 'lines')
            max_messages: Maximum number of messages to replay
            
        Returns:
            Dictionary with replay statistics
        """
        dlq_topic = f"invalid.{domain}.dlq"
        target_topic = f"raw.{domain}"
        
        return self.replay_dlq_messages(
            dlq_topic=dlq_topic,
            target_topic=target_topic,
            max_messages=max_messages
        )
    
    def get_dlq_message_count(self, dlq_topic: str) -> int:
        """
        Get the count of messages in a DLQ topic.
        
        Args:
            dlq_topic: DLQ topic name
            
        Returns:
            Number of messages in the topic
        """
        try:
            consumer = KafkaConsumer(
                dlq_topic,
                bootstrap_servers=self.bootstrap_servers,
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                consumer_timeout_ms=1000
            )
            
            # Get partition assignments
            partitions = consumer.partitions_for_topic(dlq_topic)
            if not partitions:
                return 0
            
            # Calculate total messages across all partitions
            total_messages = 0
            for partition in partitions:
                tp = (dlq_topic, partition)
                consumer.assign([tp])
                
                # Get beginning and end offsets
                beginning = consumer.beginning_offsets([tp])[tp]
                end = consumer.end_offsets([tp])[tp]
                
                total_messages += (end - beginning)
            
            consumer.close()
            return total_messages
            
        except Exception as e:
            logger.error(f"Error getting DLQ message count: {e}")
            return 0
    
    def list_dlq_topics(self) -> List[Dict[str, any]]:
        """
        List all DLQ topics and their message counts.
        
        Returns:
            List of dictionaries with DLQ topic information
        """
        dlq_topics = [
            "invalid.customers.dlq",
            "invalid.orders.dlq",
            "invalid.lines.dlq"
        ]
        
        result = []
        for topic in dlq_topics:
            count = self.get_dlq_message_count(topic)
            domain = topic.replace("invalid.", "").replace(".dlq", "")
            
            result.append({
                "topic": topic,
                "domain": domain,
                "message_count": count,
                "target_topic": f"raw.{domain}"
            })
        
        return result
    
    def close(self):
        """Close producer connection."""
        if self.producer:
            self.producer.close()
            self.producer = None
