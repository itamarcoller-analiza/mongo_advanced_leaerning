"""MySQL Analytics Service - Kafka Consumer Entry Point."""

import logging

from src.kafka.consumer import KafkaConsumer
from src.consumers.auth_consumer import AuthConsumer
from shared.kafka.topics import Topic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Start the MySQL analytics consumer."""
    logger.info("MySQL Analytics Service starting...")

    consumer = KafkaConsumer(group_id="mysql-analytics-service")

    # Register auth consumer handlers
    auth_consumer = AuthConsumer()
    for event_type, handler in auth_consumer.get_handlers().items():
        consumer.register_handler(event_type, handler)

    # Subscribe only to user topic (auth events)
    consumer.subscribe([Topic.USER])
    consumer.start()


if __name__ == "__main__":
    main()
