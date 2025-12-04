from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
import os

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'bigquery_load',
    default_args=default_args,
    description='Chargement des données traitées dans BigQuery',
    schedule_interval='@daily',
    catchup=False
)

# Variables d'environnement
PROJECT_ROOT = "/opt/airflow/project"  # À adapter selon le montage Docker
SPARK_APP_PATH = f"{PROJECT_ROOT}/spark/batch"
SCRIPTS_PATH = f"{PROJECT_ROOT}/scripts/spark"

# Tâches Spark
load_offers_task = SparkSubmitOperator(
    task_id='load_job_offers',
    application=f"{SPARK_APP_PATH}/load_to_bigquery.py",
    conn_id='spark_default',
    conf={
        'spark.sql.adaptive.enabled': 'true',
        'spark.sql.adaptive.coalescePartitions.enabled': 'true',
        'spark.hadoop.fs.s3a.endpoint': 'http://minio:9000',
        'spark.hadoop.fs.s3a.access.key': 'minioadmin',
        'spark.hadoop.fs.s3a.secret.key': 'minioadmin123',
        'spark.hadoop.fs.s3a.path.style.access': 'true',
        'spark.jars.packages': 'com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2'
    },
    env_vars={
        'GCP_PROJECT_ID': 'bigdata-jobmatching-test',
        'BIGQUERY_DATASET': 'jobmatching_dw',
        'MINIO_BUCKET': 'processed-data',
        'GOOGLE_APPLICATION_CREDENTIALS': '/opt/airflow/credentials/bq-service-account.json'
    },
    dag=dag
)

# TODO: Créer consume_cvs.py (Phase 4 manquante)
# load_cvs_task = SparkSubmitOperator(
#     task_id='load_cvs',
#     application=f"{SPARK_APP_PATH}/consume_cvs.py",  # À créer
#     conn_id='spark_default',
#     conf={
#         'spark.sql.adaptive.enabled': 'true',
#         'spark.sql.adaptive.coalescePartitions.enabled': 'true',
#         'spark.hadoop.fs.s3a.endpoint': 'http://minio:9000',
#         'spark.hadoop.fs.s3a.access.key': 'minioadmin',
#         'spark.hadoop.fs.s3a.secret.key': 'minioadmin123',
#         'spark.hadoop.fs.s3a.path.style.access': 'true',
#         'spark.jars.packages': 'com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2'
#     },
#     env_vars={
#         'GCP_PROJECT_ID': 'bigdata-jobmatching-test',
#         'BIGQUERY_DATASET': 'jobmatching_dw',
#         'MINIO_BUCKET': 'processed-data',
#         'GOOGLE_APPLICATION_CREDENTIALS': '/opt/airflow/credentials/bq-service-account.json'
#     },
#     dag=dag
# )

# Tâche temporaire pour les CVs (sera remplacée quand consume_cvs.py sera créé)
load_cvs_task = PythonOperator(
    task_id='load_cvs',
    python_callable=lambda: print("TODO: Implémenter chargement CVs"),
    dag=dag
)

# Dépendances
load_offers_task >> load_cvs_task