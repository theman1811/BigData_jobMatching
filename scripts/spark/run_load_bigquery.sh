#!/bin/bash
# ============================================
# Script de lancement - Spark Batch Load BigQuery
# ============================================
# Lance le job Spark Batch qui charge les données vers BigQuery

set -e  # Arrêter le script en cas d'erreur

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPARK_JOB="$PROJECT_ROOT/spark/batch/load_to_bigquery.py"
SPARK_MASTER="spark://spark-master:7077"
DOCKER_NETWORK="bigdata_network"

echo "🚀 Lancement du chargement Spark Batch - BigQuery"
echo "📁 Projet: $PROJECT_ROOT"
echo "📄 Job: $SPARK_JOB"
echo "🎯 Master: $SPARK_MASTER"

# Vérifier que le fichier existe
if [ ! -f "$SPARK_JOB" ]; then
    echo "❌ Erreur: Fichier $SPARK_JOB introuvable"
    exit 1
fi

# Variables d'environnement BigQuery
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-noble-anvil-479619-h9}"
export BIGQUERY_DATASET="${BIGQUERY_DATASET:-jobmatching_dw}"
export MINIO_BUCKET="${MINIO_BUCKET:-processed-data}"

# Vérifier les credentials GCP
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "⚠️  WARNING: GOOGLE_APPLICATION_CREDENTIALS non défini"
    echo "   Le job pourrait échouer si les credentials ne sont pas configurés dans Spark"
fi

# Commande Docker pour exécuter le job Spark
SPARK_SUBMIT_CMD="docker exec bigdata_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --packages org.apache.hadoop:hadoop-aws:3.3.4,com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2 \
    --conf spark.driver.memory=2g \
    --conf spark.executor.memory=2g \
    --conf spark.sql.adaptive.enabled=true \
    --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
    --conf spark.hadoop.fs.s3a.access.key=minioadmin \
    --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
    /opt/spark-apps/batch/load_to_bigquery.py"

echo "⚡ Commande Spark Submit:"
echo "$SPARK_SUBMIT_CMD"
echo ""

# Exécuter la commande
echo "🎬 Démarrage du job..."
eval "$SPARK_SUBMIT_CMD"

echo "✅ Job terminé"
