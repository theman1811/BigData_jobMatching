#!/bin/bash

# ============================================
# Script de statut - BigData Platform
# ============================================

echo "📊 Statut de la plateforme Big Data"
echo "===================================="
echo ""

# Vérifier que Docker est lancé
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker n'est pas lancé!"
    exit 1
fi

# Statut des conteneurs
echo "🐳 Conteneurs Docker:"
echo ""
docker-compose ps

echo ""
echo "📌 Interfaces Web disponibles:"
echo "   ✅ Kafka UI:         http://localhost:8080"
echo "   ✅ MinIO Console:    http://localhost:9001 (minioadmin / minioadmin123)"
echo "   ✅ Spark Master:     http://localhost:8082"
echo "   ✅ Spark Worker 1:   http://localhost:8083"
echo "   ✅ Spark Worker 2:   http://localhost:8084"
echo "   ✅ Airflow:          http://localhost:8085 (airflow / airflow)"
echo "   ✅ Superset:         http://localhost:8088 (admin / admin)"
echo "   ✅ Jupyter:          http://localhost:8888 (token: bigdata2024)"
echo ""
echo "🏗️  Architecture modernisée:"
echo "   • Kafka KRaft (sans Zookeeper)"
echo "   • MinIO (Data Lake S3)"
echo "   • Apache Superset (BI open-source)"
echo "   • Couche de scraping intégrée"
echo ""

# Utilisation des ressources
echo "💾 Utilisation des ressources:"
echo ""
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker-compose ps -q)

echo ""

