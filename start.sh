#!/bin/bash

# ============================================
# Script de démarrage - BigData Platform
# ============================================

echo "🚀 Démarrage de la plateforme Big Data..."
echo ""

# Vérifier que Docker est lancé
if ! docker info > /dev/null 2>&1; then
    echo "❌ Erreur: Docker n'est pas lancé!"
    echo "👉 Veuillez démarrer Docker Desktop et réessayer."
    exit 1
fi

# Créer les dossiers nécessaires s'ils n'existent pas
echo "📁 Création des dossiers nécessaires..."
mkdir -p ./airflow/logs ./airflow/dags ./airflow/plugins
mkdir -p ./data/raw ./data/processed ./data/sample ./data/scraped
mkdir -p ./notebooks/exploration
mkdir -p ./spark/streaming ./spark/batch
mkdir -p ./kafka/producers ./kafka/consumers ./kafka/schemas
mkdir -p ./config
mkdir -p ./docker/postgres ./docker/scrapers

# Définir les permissions pour Airflow
echo "🔐 Configuration des permissions..."
chmod -R 777 ./airflow/logs ./airflow/dags ./airflow/plugins 2>/dev/null || true

# Démarrer tous les services
echo ""
echo "🐳 Démarrage des conteneurs Docker..."
echo ""
docker-compose up -d

# Attendre que les services soient prêts
echo ""
echo "⏳ Attente du démarrage des services (30 secondes)..."
sleep 30

# Vérifier le statut
echo ""
echo "📊 Statut des services:"
docker-compose ps

echo ""
echo "✅ Plateforme Big Data démarrée!"
echo ""
echo "📌 Accès aux interfaces Web:"
echo "   • Kafka UI:         http://localhost:8080"
echo "   • MinIO Console:    http://localhost:9001 (user: minioadmin, password: minioadmin123)"
echo "   • Spark Master:     http://localhost:8082"
echo "   • Spark Worker 1:   http://localhost:8083"
echo "   • Spark Worker 2:   http://localhost:8084"
echo "   • Airflow:          http://localhost:8085 (user: airflow, password: airflow)"
echo "   • Superset:         http://localhost:8088 (user: admin, password: admin)"
echo "   • Jupyter:          http://localhost:8888 (token: bigdata2024)"
echo ""
echo "🗄️  Architecture:"
echo "   • Data Lake:        MinIO (S3-compatible, local)"
echo "   • Data Warehouse:   BigQuery (à configurer)"
echo "   • Streaming:        Kafka KRaft (sans Zookeeper!)"
echo "   • Processing:       Spark Cluster (1 Master + 2 Workers)"
echo "   • Orchestration:    Airflow"
echo "   • BI:               Apache Superset"
echo ""
echo "📝 Commandes utiles:"
echo "   • Arrêter:    ./stop.sh"
echo "   • Voir logs:  docker-compose logs -f [service]"
echo "   • Restart:    docker-compose restart [service]"
echo ""

