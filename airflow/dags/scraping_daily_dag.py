from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.state import DagRunState
from docker.types import Mount
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
SCRAPERS_IMAGE = "bigdata_jobmatching-scrapers"
SCRAPED_OUTPUT_DIR = os.getenv("SCRAPED_OUTPUT_DIR", f"{PROJECT_ROOT}/data/scraped")
HOST_PROJECT_ROOT = os.getenv("HOST_PROJECT_ROOT", "/opt/airflow")
STRICT_VALIDATION = os.getenv("SCRAPED_VALIDATION_STRICT", "false").lower() == "true"

# Variables partagées pour les conteneurs de scraping déclenchés via DockerOperator
SCRAPER_ENV = {
    "KAFKA_BOOTSTRAP_SERVERS": "kafka:29092",
    "KAFKA_SCHEMA_REGISTRY_URL": "http://schema-registry:8081",
    "MINIO_ENDPOINT": "http://minio:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin123",
    "MINIO_BUCKET_JOBS": "scraped-jobs",
    "MINIO_BUCKET_CVS": "scraped-cvs",
    "SCRAPING_DELAY_MIN": "2",
    "SCRAPING_DELAY_MAX": "5",
    "USER_AGENT_ROTATE": "true",
    "USE_PROXY": "false",
    "KAFKA_TOPIC_JOBS_RAW": "job-offers-raw",
    "KAFKA_TOPIC_CVS_RAW": "cvs-raw",
    "KAFKA_TOPIC_SCRAPING_ERRORS": "scraping-errors",
}

# Montage des sources de scrapers et des données dans le conteneur lancé
SCRAPER_MOUNTS = [
    Mount(source=f"{HOST_PROJECT_ROOT}/kafka/producers", target="/app/producers", type="bind"),
    Mount(source=f"{HOST_PROJECT_ROOT}/data/scraped", target="/app/data/scraped", type="bind"),
]

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
scrape_educarriere = DockerOperator(
    task_id='scrape_educarriere',
    image=SCRAPERS_IMAGE,
    command="python /app/producers/run_scraper.py --scraper educarriere --max-pages 10",
    api_version="auto",
    docker_url="unix://var/run/docker.sock",
    network_mode="bigdata_network",
    environment=SCRAPER_ENV,
    mounts=SCRAPER_MOUNTS,
    auto_remove=True,
    mount_tmp_dir=False,
    dag=dag,
    execution_timeout=timedelta(hours=1),
)

# 2. Scraper Macarrierepro
scrape_macarrierepro = DockerOperator(
    task_id='scrape_macarrierepro',
    image=SCRAPERS_IMAGE,
    command="python /app/producers/run_scraper.py --scraper macarrierepro --max-pages 20",
    api_version="auto",
    docker_url="unix://var/run/docker.sock",
    network_mode="bigdata_network",
    environment=SCRAPER_ENV,
    mounts=SCRAPER_MOUNTS,
    auto_remove=True,
    mount_tmp_dir=False,
    dag=dag,
    execution_timeout=timedelta(hours=1),
)

# 3. Scraper Emploi.ci
scrape_emploi_ci = DockerOperator(
    task_id='scrape_emploi_ci',
    image=SCRAPERS_IMAGE,
    command="python /app/producers/run_scraper.py --scraper emploi_ci --max-pages 20",
    api_version="auto",
    docker_url="unix://var/run/docker.sock",
    network_mode="bigdata_network",
    environment=SCRAPER_ENV,
    mounts=SCRAPER_MOUNTS,
    auto_remove=True,
    mount_tmp_dir=False,
    dag=dag,
    execution_timeout=timedelta(hours=1),
)

# 4. Scraper LinkedIn (optionnel - peut échouer)
scrape_linkedin = DockerOperator(
    task_id='scrape_linkedin',
    image=SCRAPERS_IMAGE,
    command="python /app/producers/run_scraper.py --scraper linkedin --max-pages 20",
    api_version="auto",
    docker_url="unix://var/run/docker.sock",
    network_mode="bigdata_network",
    environment=SCRAPER_ENV,
    mounts=SCRAPER_MOUNTS,
    auto_remove=True,
    mount_tmp_dir=False,
    dag=dag,
    execution_timeout=timedelta(hours=2),
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
