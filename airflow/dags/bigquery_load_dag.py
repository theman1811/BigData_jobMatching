from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.exceptions import AirflowSkipException
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable
from pathlib import Path
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

# Variables d'environnement / Airflow Variables
# Par défaut, le projet est monté dans /opt/airflow
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/airflow")
SPARK_APP_PATH = f"{PROJECT_ROOT}/spark/batch"
SCRIPTS_PATH = f"{PROJECT_ROOT}/scripts/spark"

MINIO_BUCKET = Variable.get("MINIO_BUCKET", default_var=os.getenv("MINIO_BUCKET", "processed-data"))
GCP_PROJECT_ID = Variable.get("GCP_PROJECT_ID", default_var=os.getenv("GCP_PROJECT_ID", "noble-anvil-479619-h9"))
BIGQUERY_DATASET = Variable.get("BIGQUERY_DATASET", default_var=os.getenv("BIGQUERY_DATASET", "jobmatching_dw"))
GOOGLE_CREDS = Variable.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    default_var=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/opt/airflow/credentials/bq-service-account.json")
)


def check_offers_ready(**context):
    """Valide la configuration d'entrée pour les offres avant le chargement."""
    input_path = f"s3a://{MINIO_BUCKET}/jobs_parsed"
    print(f"Entrée attendue pour les offres: {input_path}")
    return input_path


def check_cvs_ready(**context):
    """Vérifie si la pipeline CVs existe. Sinon, saute la tâche."""
    consume_cvs_script = Path(PROJECT_ROOT) / "spark" / "streaming" / "consume_cvs.py"
    if not consume_cvs_script.exists():
        raise AirflowSkipException(
            "Pipeline CVs non disponible (consume_cvs.py manquant) - tâche sautée."
        )
    print("Pipeline CVs détectée, ajouter le chargement BigQuery lorsque prête.")
    return str(consume_cvs_script)

# Tâches de préparation
check_offers_task = PythonOperator(
    task_id='check_offers_ready',
    python_callable=check_offers_ready,
    dag=dag
)

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
        'GCP_PROJECT_ID': GCP_PROJECT_ID,
        'BIGQUERY_DATASET': BIGQUERY_DATASET,
        'MINIO_BUCKET': MINIO_BUCKET,
        'GOOGLE_APPLICATION_CREDENTIALS': GOOGLE_CREDS
    },
    dag=dag
)

check_cvs_task = PythonOperator(
    task_id='check_cvs_ready',
    python_callable=check_cvs_ready,
    dag=dag
)

# Placeholder pour le chargement des CVs (sera remplacé dès que le job sera disponible)
load_cvs_task = EmptyOperator(
    task_id='load_cvs_placeholder',
    dag=dag,
    trigger_rule='none_failed_min_one_success'
)

# Dépendances
check_offers_task >> load_offers_task >> check_cvs_task >> load_cvs_task