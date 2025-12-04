from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.sensors.external_task import ExternalTaskSensor
from pathlib import Path
import json
import os

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
    'execution_timeout': timedelta(hours=2)
}

dag = DAG(
    'processing_spark',
    default_args=default_args,
    description='Processing Spark des données scrapées (parsing, enrichment, déduplication)',
    schedule_interval='0 4 * * *',  # 4h du matin (après scraping à 2h)
    catchup=False,
    tags=['spark', 'processing', 'batch']
)

# Variables d'environnement
PROJECT_ROOT = "/opt/airflow/project"  # À adapter selon le montage Docker
SPARK_APP_PATH = f"{PROJECT_ROOT}/spark/batch"
SCRIPTS_PATH = f"{PROJECT_ROOT}/scripts/spark"
PROCESSED_DATA_DIR = Path(os.getenv("PROCESSED_DATA_DIR", f"{PROJECT_ROOT}/data/processed"))
STRICT_VALIDATION = os.getenv("PROCESSING_VALIDATION_STRICT", "false").lower() == "true"

# Configuration commune Spark
SPARK_CONF = {
    'spark.sql.adaptive.enabled': 'true',
    'spark.sql.adaptive.coalescePartitions.enabled': 'true',
    'spark.hadoop.fs.s3a.endpoint': 'http://minio:9000',
    'spark.hadoop.fs.s3a.access.key': 'minioadmin',
    'spark.hadoop.fs.s3a.secret.key': 'minioadmin123',
    'spark.hadoop.fs.s3a.path.style.access': 'true',
    'spark.jars.packages': 'com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2'
}

SPARK_ENV_VARS = {
    'GCP_PROJECT_ID': 'bigdata-jobmatching-test',
    'BIGQUERY_DATASET': 'jobmatching_dw',
    'MINIO_BUCKET': 'processed-data',
    'GOOGLE_APPLICATION_CREDENTIALS': '/opt/airflow/credentials/bq-service-account.json'
}

def check_processing_quality(**context):
    """Contrôle basique des sorties de processing.

    Vérifie la présence des répertoires de sortie clés. En mode strict
    (PROCESSING_VALIDATION_STRICT=true), l'absence d'un répertoire obligatoire
    fait échouer la tâche.
    """
    expected_dirs = {
        "jobs_parsed": True,
        "jobs": False,              # parquet streaming
        "skills_enriched": False,   # si étape d'enrichissement
        "salaries_enriched": False,
        "deduplicated": False,
        "sectors_enriched": False,
    }

    if not PROCESSED_DATA_DIR.exists():
        msg = f"Répertoire de données traitées introuvable: {PROCESSED_DATA_DIR}"
        if STRICT_VALIDATION:
            raise FileNotFoundError(msg)
        print(f"⚠️ {msg}")
        return

    stats = {}
    for folder, required in expected_dirs.items():
        path = PROCESSED_DATA_DIR / folder
        file_count = len([p for p in path.rglob("*.parquet")]) if path.exists() else 0
        stats[folder] = {"required": required, "files": file_count}

        if required and file_count == 0 and STRICT_VALIDATION:
            raise ValueError(f"Aucune sortie détectée pour {folder}")

    print("📊 Statistiques processing:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

# ============================================
# JOBS SPARK BATCH (séquentiels)
# ============================================

# 1. Parsing des offres HTML
spark_parse_jobs = SparkSubmitOperator(
    task_id='spark_parse_jobs',
    application=f"{SPARK_APP_PATH}/parse_jobs.py",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

# 2. Extraction des compétences (NLP)
spark_extract_skills = SparkSubmitOperator(
    task_id='spark_extract_skills',
    application=f"{SPARK_APP_PATH}/extract_skills.py",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

# 3. Extraction des salaires
spark_extract_salary = SparkSubmitOperator(
    task_id='spark_extract_salary',
    application=f"{SPARK_APP_PATH}/extract_salary.py",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

# 4. Déduplication
spark_deduplicate = SparkSubmitOperator(
    task_id='spark_deduplicate',
    application=f"{SPARK_APP_PATH}/deduplicate.py",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

# 5. Extraction des secteurs (optionnel)
spark_extract_sectors = SparkSubmitOperator(
    task_id='spark_extract_sectors',
    application=f"{SPARK_APP_PATH}/extract_sectors.py",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

# ============================================
# CONTRÔLE QUALITÉ
# ============================================

check_processing_quality_task = PythonOperator(
    task_id='check_processing_quality',
    python_callable=check_processing_quality,
    dag=dag
)

# ============================================
# DÉPENDANCES SÉQUENTIELLES
# ============================================

# Ordre d'exécution obligatoire
spark_parse_jobs >> spark_extract_skills >> spark_extract_salary >> spark_deduplicate >> spark_extract_sectors >> check_processing_quality_task
