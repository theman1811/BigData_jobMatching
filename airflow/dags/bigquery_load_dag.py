from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

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

def load_job_offers():
    """Charge les offres d'emploi dans BigQuery"""
    # Code pour charger depuis MinIO vers BigQuery
    pass

def load_cvs():
    """Charge les CVs dans BigQuery"""
    # Code pour charger depuis MinIO vers BigQuery
    pass

# Tâches
load_offers_task = PythonOperator(
    task_id='load_job_offers',
    python_callable=load_job_offers,
    dag=dag
)

load_cvs_task = PythonOperator(
    task_id='load_cvs',
    python_callable=load_cvs,
    dag=dag
)

# Dépendances
load_offers_task >> load_cvs_task