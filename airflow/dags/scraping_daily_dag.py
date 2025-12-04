from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.state import DagRunState
from pathlib import Path
import json
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
# Le volume du projet est monté sous /opt/airflow (voir docker-compose)
PROJECT_ROOT = "/opt/airflow"
SCRAPERS_SCRIPT = f"{PROJECT_ROOT}/kafka/producers/run_scraper.py"
SCRAPED_OUTPUT_DIR = os.getenv("SCRAPED_OUTPUT_DIR", f"{PROJECT_ROOT}/data/scraped")
STRICT_VALIDATION = os.getenv("SCRAPED_VALIDATION_STRICT", "false").lower() == "true"

def check_data_quality(**context):
    """Vérifie la présence minimale de données scrapées par source.

    Si STRICT_VALIDATION=true, les sources obligatoires (hors LinkedIn) doivent
    contenir au moins un fichier sinon la tâche échoue.
    """
    sources = {
        "educarriere": True,
        "macarrierepro": True,
        "emploi_ci": True,
        "linkedin": False,  # optionnel
    }

    base_path = Path(SCRAPED_OUTPUT_DIR)
    stats = {}

    if not base_path.exists():
        msg = f"Répertoire de scraping introuvable: {base_path}"
        if STRICT_VALIDATION:
            raise FileNotFoundError(msg)
        print(f"⚠️ {msg}")
        return

    for source, required in sources.items():
        source_dir = base_path / source
        file_count = len([f for f in source_dir.rglob("*") if f.is_file()]) if source_dir.exists() else 0
        stats[source] = {"required": required, "files": file_count}

        if required and file_count == 0 and STRICT_VALIDATION:
            raise ValueError(f"Aucune donnée trouvée pour la source obligatoire: {source}")

    print("📊 Statistiques scraping:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

def notify_completion(**context):
    """Notification simple de fin de scraping."""
    print("✅ Scraping terminé avec succès - toutes les tâches amont sont terminées.")

# ============================================
# TÂCHES DE SCRAPING
# ============================================

# 1. Scraper Educarriere
scrape_educarriere = BashOperator(
    task_id='scrape_educarriere',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --scraper educarriere',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 2. Scraper Macarrierepro
scrape_macarrierepro = BashOperator(
    task_id='scrape_macarrierepro',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --scraper macarrierepro',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 3. Scraper Emploi.ci
scrape_emploi_ci = BashOperator(
    task_id='scrape_emploi_ci',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --scraper emploi_ci',
    dag=dag,
    execution_timeout=timedelta(hours=1)
)

# 4. Scraper LinkedIn (optionnel - peut échouer)
scrape_linkedin = BashOperator(
    task_id='scrape_linkedin',
    bash_command=f'cd {PROJECT_ROOT}/kafka/producers && python run_scraper.py --scraper linkedin || echo "LinkedIn scraping failed, continuing..."',
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
