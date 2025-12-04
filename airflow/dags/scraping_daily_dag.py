from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.state import DagRunState
import os

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=15),
    'execution_timeout': timedelta(hours=4)
}

dag = DAG(
    'scraping_daily',
    default_args=default_args,
    description='Scraping quotidien des offres d\'emploi depuis les sites ivoiriens',
    schedule_interval='0 2 * * *',  # 2h du matin tous les jours
    catchup=False,
    tags=['scraping', 'daily', 'job_offers']
)

# Variables d'environnement
PROJECT_ROOT = "/opt/airflow/project"  # À adapter selon le montage Docker
SCRAPERS_SCRIPT = f"{PROJECT_ROOT}/kafka/producers/run_scraper.py"

def check_data_quality():
    """Vérifie la qualité des données scrapées"""
    # TODO: Implémenter vérification qualité
    # - Vérifier nombre d'offres par source
    # - Vérifier format des données
    # - Vérifier taux d'erreur
    print("✅ Vérification qualité des données (TODO: implémenter)")

def notify_completion():
    """Notification de fin de scraping"""
    # TODO: Implémenter notification (email, Slack, etc.)
    print("✅ Scraping terminé avec succès")

# ============================================
# TÂCHES DE SCRAPING
# ============================================

# 1. Scraper Educarriere
scrape_educarriere = BashOperator(
    task_id='scrape_educarriere',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --source educarriere',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 2. Scraper Macarrierepro
scrape_macarrierepro = BashOperator(
    task_id='scrape_macarrierepro',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --source macarrierepro',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 3. Scraper Emploi.ci
scrape_emploi_ci = BashOperator(
    task_id='scrape_emploi_ci',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --source emploi_ci',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 4. Scraper LinkedIn (optionnel - peut échouer)
scrape_linkedin = BashOperator(
    task_id='scrape_linkedin',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --source linkedin || echo "LinkedIn scraping failed, continuing..."',
    dag=dag,
    execution_timeout=timedelta(hours=2)
)

# ============================================
# TÂCHES DE CONTRÔLE ET QUALITÉ
# ============================================

# Attendre que tous les scrapers soient terminés
wait_all_scrapers = PythonOperator(
    task_id='wait_all_scrapers',
    python_callable=lambda: print("✅ Tous les scrapers terminés"),
    dag=dag
)

# Vérification qualité des données
check_quality = PythonOperator(
    task_id='check_data_quality',
    python_callable=check_data_quality,
    dag=dag
)

# Notification de fin
notify_completion_task = PythonOperator(
    task_id='notify_completion',
    python_callable=notify_completion,
    dag=dag
)

# ============================================
# DÉPENDANCES
# ============================================

# Les scrapers peuvent tourner en parallèle
[scrape_educarriere, scrape_macarrierepro, scrape_emploi_ci, scrape_linkedin] >> wait_all_scrapers

# Puis vérification qualité
wait_all_scrapers >> check_quality

# Enfin notification
check_quality >> notify_completion_task
