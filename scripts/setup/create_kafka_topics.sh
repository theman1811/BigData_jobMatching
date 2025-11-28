#!/bin/bash

# ============================================
# Script de création des topics Kafka
# ============================================

echo "📋 Création des topics Kafka par défaut..."
echo ""

# Topics de test
topics=(
    "events-raw:3:1"
    "events-processed:3:1"
    "logs-raw:3:1"
    "metrics-raw:3:1"
)

for topic_config in "${topics[@]}"; do
    IFS=':' read -r topic partitions replication <<< "$topic_config"
    
    echo "Création du topic: $topic (partitions: $partitions, replication: $replication)"
    
    docker exec bigdata_kafka kafka-topics \
        --create \
        --bootstrap-server localhost:9092 \
        --topic $topic \
        --partitions $partitions \
        --replication-factor $replication \
        --if-not-exists \
        --config retention.ms=604800000
done

echo ""
echo "✅ Topics créés!"
echo ""
echo "📝 Pour lister les topics:"
echo "   docker exec bigdata_kafka kafka-topics --list --bootstrap-server localhost:9092"
echo ""

