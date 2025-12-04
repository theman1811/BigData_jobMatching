from datetime import datetime, timedelta
import os
import shutil
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0
}

dag = DAG(
    'platform_monitoring',
    default_args=default_args,
    description='Surveillance légère du pipeline (Kafka, MinIO, Spark)',
    schedule_interval='*/30 * * * *',  # Toutes les 30 minutes
    catchup=False,
    tags=['monitoring']
)


def check_kafka_lag(**context):
    """Vérifie la configuration Kafka (placeholder sans requête réseau)."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    print(f"Kafka bootstrap configuré sur: {bootstrap}")
    print("TODO: brancher une vérification réelle du consumer lag (Prometheus/CLI).")


def check_minio_space(**context):
    """Mesure l'espace disque disponible sur le volume MinIO (si monté)."""
    minio_dir = os.getenv("MINIO_DATA_DIR", "/data/minio")
    if not os.path.exists(minio_dir):
        print(f"⚠️ Volume MinIO introuvable localement: {minio_dir}")
        return

    usage = shutil.disk_usage(minio_dir)
    pct_used = round((usage.used / usage.total) * 100, 2) if usage.total else 0
    print(f"MinIO: {pct_used}% utilisé ({usage.used / 1e9:.2f} GB / {usage.total / 1e9:.2f} GB)")


def check_spark_jobs(**context):
    """Placeholder de vérification Spark."""
    spark_master = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
    print(f"Spark master configuré sur: {spark_master}")
    print("TODO: interroger l'API Spark Master pour lister les jobs actifs.")


def alert_if_issues(**context):
    """Point central pour alerter (placeholder)."""
    print("Aucune alerte configurée. TODO: brancher email/Slack/Prometheus.")


check_kafka_task = PythonOperator(
    task_id='check_kafka_lag',
    python_callable=check_kafka_lag,
    dag=dag
)

check_minio_task = PythonOperator(
    task_id='check_minio_space',
    python_callable=check_minio_space,
    dag=dag
)

check_spark_task = PythonOperator(
    task_id='check_spark_jobs',
    python_callable=check_spark_jobs,
    dag=dag
)

alert_task = PythonOperator(
    task_id='alert_if_issues',
    python_callable=alert_if_issues,
    dag=dag
)

[check_kafka_task, check_minio_task, check_spark_task] >> alert_task

