# Kafka Development Commands
# Usage: make <target>

.PHONY: help kafka-up kafka-down kafka-logs kafka-ui topics-list topics-describe \
        consume-user consume-order outbox-publisher clean

# Default target
help:
	@echo "Kafka Development Commands"
	@echo "=========================="
	@echo ""
	@echo "Infrastructure:"
	@echo "  kafka-up          Start Kafka and UI"
	@echo "  kafka-down        Stop Kafka and UI"
	@echo "  kafka-logs        View Kafka logs"
	@echo "  kafka-ui          Open Kafka UI in browser"
	@echo "  clean             Remove all Kafka data"
	@echo ""
	@echo "Topics:"
	@echo "  topics-list       List all topics"
	@echo "  topics-describe   Describe all topics"
	@echo "  topics-create     Create all topics (runs init container)"
	@echo ""
	@echo "Development:"
	@echo "  consume-user      Consume from sc.domain.user"
	@echo "  consume-order     Consume from sc.domain.order"
	@echo "  outbox-publisher  Run outbox publisher worker"
	@echo ""

# Infrastructure
kafka-up:
	docker-compose -f docker/docker-compose.kafka.yml up -d kafka kafka-ui
	@echo "Waiting for Kafka to be healthy..."
	@sleep 5
	docker-compose -f docker/docker-compose.kafka.yml up kafka-init
	@echo ""
	@echo "Kafka UI available at: http://localhost:8080"

kafka-down:
	docker-compose -f docker/docker-compose.kafka.yml down

kafka-logs:
	docker-compose -f docker/docker-compose.kafka.yml logs -f kafka

kafka-ui:
	@echo "Opening Kafka UI..."
	@open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null || echo "Open http://localhost:8080 in your browser"

clean:
	docker-compose -f docker/docker-compose.kafka.yml down -v
	@echo "Kafka data removed"

# Topics
topics-list:
	docker exec sc-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

topics-describe:
	docker exec sc-kafka kafka-topics.sh --bootstrap-server localhost:9092 --describe

topics-create:
	docker-compose -f docker/docker-compose.kafka.yml up kafka-init

# Development consumers (for debugging)
consume-user:
	docker exec -it sc-kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic sc.domain.user \
		--from-beginning \
		--property print.key=true \
		--property key.separator=" | "

consume-order:
	docker exec -it sc-kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic sc.domain.order \
		--from-beginning \
		--property print.key=true \
		--property key.separator=" | "

consume-dlq:
	docker exec -it sc-kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic sc.dlq.outbox-user \
		--from-beginning \
		--property print.key=true \
		--property key.separator=" | "

# Outbox publisher
outbox-publisher:
	KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python -m kafka.outbox.publisher

# Produce test message (for debugging)
produce-test:
	@echo '{"test": "message", "timestamp": "'$$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' | \
		docker exec -i sc-kafka kafka-console-producer.sh \
			--bootstrap-server localhost:9092 \
			--topic sc.domain.user
