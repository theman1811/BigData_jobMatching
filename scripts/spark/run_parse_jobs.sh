#!/bin/bash
# ============================================
# Script de lancement - Spark Batch Parse Jobs
# ============================================
# Lance le job Spark Batch qui parse les offres d'emploi HTML

set -e  # Arrêter le script en cas d'erreur

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPARK_JOB="$PROJECT_ROOT/spark/batch/parse_jobs.py"
SPARK_MASTER="spark://spark-master:7077"
DOCKER_NETWORK="bigdata_network"

echo "🚀 Lancement du parsing Spark Batch - Offres d'emploi"
echo "📁 Projet: $PROJECT_ROOT"
echo "📄 Job: $SPARK_JOB"
echo "🎯 Master: $SPARK_MASTER"

# Vérifier que le fichier existe
if [ ! -f "$SPARK_JOB" ]; then
    echo "❌ Erreur: Fichier $SPARK_JOB introuvable"
    exit 1
fi

# Commande Docker pour exécuter le job Spark
SPARK_SUBMIT_CMD="docker exec bigdata_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --packages org.apache.hadoop:hadoop-aws:3.3.4 \
    --conf spark.driver.memory=2g \
    --conf spark.executor.memory=2g \
    --conf spark.sql.adaptive.enabled=true \
    --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
    --conf spark.hadoop.fs.s3a.access.key=minioadmin \
    --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
    /opt/spark-apps/batch/parse_jobs.py"

echo "⚡ Commande Spark Submit:"
echo "$SPARK_SUBMIT_CMD"
echo ""

# Exécuter la commande
echo "🎬 Démarrage du job..."
eval "$SPARK_SUBMIT_CMD"

echo "✅ Job terminé"
