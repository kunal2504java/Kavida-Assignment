"""
Kafka consumer for DQ violations topic.
Runs in a background thread.
"""
import json
import logging
import threading
from typing import Callable
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class ViolationsConsumer:
    """Background consumer for dq.violations topic."""
    
    def __init__(self, bootstrap_servers: str, callback: Callable):
        self.bootstrap_servers = bootstrap_servers
        self.callback = callback
        self.consumer: KafkaConsumer = None
        self.thread: threading.Thread = None
        self.running = False
    
    def start(self):
        """Start the consumer in a background thread."""
        if self.running:
            logger.warning("Consumer is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.thread.start()
        logger.info("Started violations consumer thread")
    
    def stop(self):
        """Stop the consumer thread."""
        self.running = False
        if self.consumer:
            self.consumer.close()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Stopped violations consumer thread")
    
    def _consume_loop(self):
        """Main consumption loop running in background thread."""
        try:
            # Create consumer
            self.consumer = KafkaConsumer(
                'dq.violations',
                bootstrap_servers=self.bootstrap_servers,
                group_id='dq-report-group',
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                max_poll_records=100,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            logger.info("Violations consumer ready, waiting for messages...")
            
            # Consume messages
            for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    violation = message.value
                    
                    logger.debug(
                        f"Received violation: {violation.get('message_id')} "
                        f"(domain={violation.get('domain')}, rule={violation.get('rule_name')})"
                    )
                    
                    # Call the callback to process the violation
                    self.callback(violation)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize violation message: {e}")
                except Exception as e:
                    logger.error(f"Error processing violation message: {e}", exc_info=True)
            
        except KafkaError as e:
            logger.error(f"Kafka error in consumer: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in consumer: {e}", exc_info=True)
        finally:
            if self.consumer:
                self.consumer.close()
            logger.info("Violations consumer stopped")
