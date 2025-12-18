#!/bin/bash
# Script rapide pour vérifier l'état de BigQuery et détecter les doublons

echo "=============================================="
echo "🔍 VÉRIFICATION BIGQUERY - État des doublons"
echo "=============================================="
echo ""

# Afficher le dernier run du DAG bigquery_load
echo "📊 Dernières exécutions du DAG bigquery_load:"
docker exec bigdata_airflow_scheduler airflow dags list-runs -d bigquery_load --no-backfill --output table 2>/dev/null | head -10
echo ""

# Vérifier les logs du dernier run pour voir la déduplication
echo "🔍 Recherche des messages de déduplication dans les logs récents:"
echo ""

# Chercher dans les logs Spark du dernier jour
docker exec bigdata_spark_master find /opt/spark/logs -name "*.out" -mtime -1 -exec grep -l "Vérification des offres existantes" {} \; 2>/dev/null | head -1 | xargs -I {} sh -c 'echo "📄 Fichier: {}" && grep -A 2 -E "Vérification des offres|nouvelles offres|offres existantes|Aucune nouvelle" {}'

echo ""
echo "=============================================="
echo "💡 Commandes utiles"
echo "=============================================="
echo ""
echo "1. Déclencher manuellement le DAG BigQuery:"
echo "   docker exec bigdata_airflow_scheduler airflow dags trigger bigquery_load"
echo ""
echo "2. Voir l'interface Airflow:"
echo "   http://localhost:8080"
echo ""
echo "3. Voir les logs Spark en temps réel:"
echo "   docker logs -f bigdata_spark_master"
echo ""
echo "4. Compter les fichiers dans MinIO:"
echo "   docker exec bigdata_scrapers python3 -c \\"
echo "     from minio import Minio; \\"
echo "     client = Minio('minio:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False); \\"
echo "     print(f'Scraped: {len(list(client.list_objects(\\\"scraped-jobs\\\", recursive=True)))}'); \\"
echo "     print(f'Parsed: {len([o for o in client.list_objects(\\\"processed-data\\\", prefix=\\\"jobs_parsed/\\\", recursive=True) if o.object_name.endswith(\\\".parquet\\\")])}'); \\"
echo "   \\"
echo ""
