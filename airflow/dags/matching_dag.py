from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.exceptions import AirflowSkipException
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
    'matching_pipeline',
    default_args=default_args,
    description='Calcul de matching offres-CVs et génération de recommandations',
    schedule_interval='0 8 * * *',  # 8h du matin
    catchup=False,
    tags=['matching', 'spark']
)

PROJECT_ROOT = "/opt/airflow/project"
SPARK_APP_PATH = f"{PROJECT_ROOT}/spark/batch"

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
    'GCP_PROJECT_ID': os.getenv('GCP_PROJECT_ID', 'noble-anvil-479619-h9'),
    'BIGQUERY_DATASET': os.getenv('BIGQUERY_DATASET', 'jobmatching_dw'),
    'MINIO_BUCKET': os.getenv('MINIO_BUCKET', 'processed-data'),
    # Le driver Spark s'exécute dans le conteneur Airflow, donc utiliser le chemin Airflow
    'GOOGLE_APPLICATION_CREDENTIALS': '/opt/airflow/credentials/bq-service-account.json'
}


def ensure_matching_job(**context):
    """Vérifie la présence du job Spark matching."""
    matching_script = Path(SPARK_APP_PATH) / "matching.py"
    if not matching_script.exists():
        raise AirflowSkipException(
            "Job matching non disponible (matching.py manquant) - tâche sautée."
        )
    return str(matching_script)


def summarize_results(**context):
    """Placeholder pour le post-traitement des résultats de matching."""
    output_path = f"s3a://{SPARK_ENV_VARS['MINIO_BUCKET']}/matching/"
    print(f"📂 Résultats attendus dans: {output_path}")
    print("TODO: ajouter chargement BigQuery / notifications quand matching.py sera prêt.")


def generate_recommendations(**context):
    """Placeholder pour générer des recommandations côté applicatif."""
    print("🧠 Génération de recommandations (à compléter avec l'implémentation applicative).")


check_matching_job = PythonOperator(
    task_id='check_matching_job',
    python_callable=ensure_matching_job,
    dag=dag
)

spark_matching = SparkSubmitOperator(
    task_id='spark_matching',
    application="{{ ti.xcom_pull(task_ids='check_matching_job') }}",
    conn_id='spark_default',
    conf=SPARK_CONF,
    env_vars=SPARK_ENV_VARS,
    dag=dag
)

load_matching_results = PythonOperator(
    task_id='load_matching_results',
    python_callable=summarize_results,
    dag=dag
)

generate_recommendations_task = PythonOperator(
    task_id='generate_recommendations',
    python_callable=generate_recommendations,
    dag=dag
)

check_matching_job >> spark_matching >> load_matching_results >> generate_recommendations_task

