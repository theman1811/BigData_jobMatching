#!/bin/bash
# Script de test de la déduplication BigQuery
# Ce script déclenche le DAG et surveille les logs pour vérifier la déduplication

set -e

PROJECT_DIR="/Users/nedio/Documents/programmation/school/BigData_jobMatching"
cd "$PROJECT_DIR"

echo "=============================================="
echo "🧪 TEST DE DÉDUPLICATION BIGQUERY"
echo "=============================================="
echo ""

# Vérifier que les services sont actifs
echo "🔍 Vérification des services..."
if ! docker ps | grep -q "bigdata_airflow_scheduler"; then
    echo "❌ Airflow n'est pas démarré. Lancez ./start.sh"
    exit 1
fi
echo "✅ Services actifs"
echo ""

# Compter les fichiers dans MinIO
echo "📦 État de MinIO:"
docker exec bigdata_scrapers python3 -c "
from minio import Minio
client = Minio('minio:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)
scraped = len(list(client.list_objects('scraped-jobs', recursive=True)))
print(f'   - scraped-jobs: {scraped} fichiers HTML')
try:
    parsed = len([o for o in client.list_objects('processed-data', prefix='jobs_parsed/', recursive=True) if o.object_name.endswith('.parquet')])
    print(f'   - jobs_parsed: {parsed} fichiers parquet')
except:
    print(f'   - jobs_parsed: 0 fichiers parquet')
"
echo ""

# Déclencher le DAG
echo "🚀 Déclenchement du DAG processing_spark..."
TRIGGER_OUTPUT=$(docker exec bigdata_airflow_scheduler airflow dags trigger processing_spark 2>&1)
echo "$TRIGGER_OUTPUT"

# Extraire le dag_run_id
DAG_RUN_ID=$(echo "$TRIGGER_OUTPUT" | grep -oE 'manual__[0-9T:+-]+' | head -1)

if [ -z "$DAG_RUN_ID" ]; then
    echo "⚠️  Impossible de déterminer le dag_run_id. Continuons quand même..."
    DAG_RUN_ID="latest"
fi

echo "📝 DAG Run ID: $DAG_RUN_ID"
echo ""

# Attendre un peu que le DAG démarre
echo "⏳ Attente du démarrage du DAG (30 secondes)..."
sleep 30

# Fonction pour récupérer les logs d'une tâche
get_task_logs() {
    local task_id=$1
    echo ""
    echo "📋 Logs de la tâche: $task_id"
    echo "----------------------------------------"
    
    # Essayer de récupérer les logs
    docker exec bigdata_airflow_scheduler airflow tasks logs processing_spark "$task_id" "$DAG_RUN_ID" 2>/dev/null || {
        echo "⚠️  Logs pas encore disponibles pour $task_id"
        return 1
    }
}

# Attendre que la tâche spark_parse_jobs soit terminée
echo "⏳ Attente de la fin de spark_parse_jobs..."
MAX_WAIT=300  # 5 minutes max
ELAPSED=0
INTERVAL=15

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATE=$(docker exec bigdata_airflow_scheduler airflow tasks state processing_spark spark_parse_jobs "$DAG_RUN_ID" 2>/dev/null || echo "pending")
    
    echo "   État de spark_parse_jobs: $STATE (${ELAPSED}s/${MAX_WAIT}s)"
    
    if [ "$STATE" = "success" ]; then
        echo "✅ spark_parse_jobs terminé avec succès"
        break
    elif [ "$STATE" = "failed" ]; then
        echo "❌ spark_parse_jobs a échoué"
        get_task_logs "spark_parse_jobs"
        exit 1
    elif [ "$STATE" = "running" ]; then
        echo "   ⏳ Tâche en cours d'exécution..."
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "⏰ Timeout atteint. Le DAG prend trop de temps."
    echo "Vous pouvez vérifier manuellement sur http://localhost:8080"
    exit 1
fi

echo ""
echo "=============================================="
echo "📊 RÉSULTATS DU TEST"
echo "=============================================="
echo ""

# Afficher l'état final du DAG
echo "📈 État final du DAG:"
docker exec bigdata_airflow_scheduler airflow dags state processing_spark "$DAG_RUN_ID" 2>/dev/null || echo "État inconnu"
echo ""

# Compter les fichiers parsés après exécution
echo "📦 État de MinIO après processing:"
docker exec bigdata_scrapers python3 -c "
from minio import Minio
client = Minio('minio:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)
try:
    parsed = len([o for o in client.list_objects('processed-data', prefix='jobs_parsed/', recursive=True) if o.object_name.endswith('.parquet')])
    print(f'   - jobs_parsed: {parsed} fichiers parquet')
except:
    print(f'   - jobs_parsed: 0 fichiers parquet')
"
echo ""

echo "=============================================="
echo "✅ Test terminé !"
echo "=============================================="
echo ""
echo "Pour voir les logs complets du DAG:"
echo "  docker exec bigdata_airflow_scheduler airflow dags show processing_spark"
echo ""
echo "Pour voir l'interface Airflow:"
echo "  http://localhost:8080"
echo ""
echo "Pour vérifier BigQuery manuellement, exécutez dans le conteneur Spark:"
echo "  docker exec bigdata_spark_master /opt/spark/bin/spark-submit --master spark://spark-master:7077 /opt/airflow/spark/batch/load_to_bigquery.py"
echo ""
