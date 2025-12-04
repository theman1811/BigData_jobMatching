from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.sensors.external_task import ExternalTaskSensor
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

def check_processing_quality():
    """Vérifie la qualité du processing"""
    # TODO: Implémenter vérifications
    # - Vérifier nombre d'offres traitées
    # - Taux de succès des extractions
    # - Cohérence des données
    print("✅ Vérification qualité du processing (TODO: implémenter)")

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
