# 🚀 Prochaines Étapes - Votre Plan d'Action

## ✅ Ce qui est Fait

Votre infrastructure Big Data est **100% configurée** :

### Infrastructure
- ✅ Docker Compose avec 17 services
- ✅ Kafka KRaft (sans Zookeeper)
- ✅ MinIO (Data Lake S3)
- ✅ Apache Spark (1 Master + 2 Workers)
- ✅ Apache Airflow
- ✅ Apache Superset
- ✅ PostgreSQL + Redis
- ✅ Jupyter avec PySpark
- ✅ Container Scrapers

### Configuration
- ✅ Tous les fichiers de config créés
- ✅ Scripts de démarrage/arrêt
- ✅ Documentation complète
- ✅ Requirements Python

### Documentation
- ✅ README.md complet
- ✅ Architecture détaillée
- ✅ Guides de démarrage
- ✅ Changelog

## 🎯 Ce qu'il Reste à Faire

### Phase 1 : Démarrage et Tests (1-2 jours)

#### 1.1 Démarrer la plateforme

```bash
# Copier .env
cp .env.example .env

# Démarrer tous les services
./start.sh

# Attendre 3-4 minutes
# Vérifier le statut
./status.sh
```

**Checklist** :
- [ ] Tous les conteneurs démarrent sans erreur
- [ ] Kafka UI accessible (http://localhost:8080)
- [ ] MinIO accessible (http://localhost:9001)
- [ ] Spark Master accessible (http://localhost:8082)
- [ ] Airflow accessible (http://localhost:8085)
- [ ] Superset accessible (http://localhost:8088)
- [ ] Jupyter accessible (http://localhost:8888)

#### 1.2 Tests basiques

**Test Kafka** :
```bash
# Créer un topic
docker exec -it bigdata_kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic test-job-offers \
  --partitions 3
```

**Test MinIO** :
- Ouvrir http://localhost:9001
- Login : minioadmin / minioadmin123
- Vérifier que les 6 buckets existent

**Test Spark + MinIO** :
- Ouvrir Jupyter : http://localhost:8888
- Exécuter le code de test dans `QUICKSTART_NEW.md`

**Résultat attendu** :
- [ ] Kafka fonctionne
- [ ] MinIO fonctionne
- [ ] Spark lit/écrit dans MinIO
- [ ] Pas d'erreurs dans les logs

### Phase 2 : Configuration BigQuery (1 jour)

#### 2.1 Créer le projet GCP

1. Aller sur https://console.cloud.google.com
2. Créer un nouveau projet : `job-matching-bigdata`
3. Activer BigQuery API
4. Créer un dataset : `job_matching_dw`

#### 2.2 Créer le Service Account

```bash
# Installer gcloud CLI si pas déjà fait
# https://cloud.google.com/sdk/docs/install

# Se connecter
gcloud auth login

# Créer le service account
gcloud iam service-accounts create bigdata-sa \
  --display-name="BigData Service Account" \
  --project=job-matching-bigdata

# Donner les permissions BigQuery
gcloud projects add-iam-policy-binding job-matching-bigdata \
  --member="serviceAccount:bigdata-sa@job-matching-bigdata.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Créer la clé JSON
gcloud iam service-accounts keys create ./config/gcp-service-account.json \
  --iam-account=bigdata-sa@job-matching-bigdata.iam.gserviceaccount.com
```

#### 2.3 Configurer les variables

```bash
# Éditer .env
nano .env

# Ajouter :
GCP_PROJECT_ID=job-matching-bigdata
GCP_DATASET_ID=job_matching_dw
GCP_SERVICE_ACCOUNT_KEY_PATH=/opt/airflow/config/gcp-service-account.json
```

#### 2.4 Créer les tables BigQuery

Exécuter dans la console BigQuery :

```sql
-- Table des offres d'emploi
CREATE TABLE job_matching_dw.fact_job_offers (
  job_id STRING NOT NULL,
  title STRING,
  company_id STRING,
  location_id STRING,
  description TEXT,
  salary_min FLOAT64,
  salary_max FLOAT64,
  contract_type STRING,
  remote_option BOOLEAN,
  skills ARRAY<STRING>,
  posted_date DATE,
  scraped_at TIMESTAMP,
  source STRING
)
PARTITION BY posted_date
CLUSTER BY company_id, location_id;

-- Table des CVs
CREATE TABLE job_matching_dw.fact_candidates (
  candidate_id STRING NOT NULL,
  skills ARRAY<STRING>,
  years_experience INT64,
  education_level STRING,
  desired_salary FLOAT64,
  location_id STRING,
  scraped_at TIMESTAMP
)
PARTITION BY DATE(scraped_at);

-- Table des compétences
CREATE TABLE job_matching_dw.dim_skills (
  skill_id STRING NOT NULL,
  skill_name STRING,
  skill_category STRING,
  created_at TIMESTAMP
);

-- Table des entreprises
CREATE TABLE job_matching_dw.dim_companies (
  company_id STRING NOT NULL,
  company_name STRING,
  industry STRING,
  size STRING,
  location STRING,
  website STRING
);

-- Table des matching
CREATE TABLE job_matching_dw.agg_matching_scores (
  job_id STRING,
  candidate_id STRING,
  match_score FLOAT64,
  skill_match_pct FLOAT64,
  salary_match_pct FLOAT64,
  location_match_pct FLOAT64,
  calculated_at TIMESTAMP
)
PARTITION BY DATE(calculated_at);
```

**Checklist** :
- [ ] Projet GCP créé
- [ ] Service Account créé
- [ ] Clé JSON téléchargée
- [ ] Variables .env configurées
- [ ] Tables BigQuery créées

### Phase 3 : Implémenter les Scrapers (3-5 jours)

#### 3.1 Créer la structure

```bash
mkdir -p kafka/producers/scrapers
mkdir -p kafka/producers/utils
```

#### 3.2 Scraper de base

Créer `kafka/producers/scrapers/base_scraper.py` :

```python
from abc import ABC, abstractmethod
from kafka import KafkaProducer
from minio import Minio
import json
import logging

class BaseJobScraper(ABC):
    """Classe abstraite pour tous les scrapers"""
    
    def __init__(self, kafka_servers, minio_endpoint):
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.minio_client = Minio(
            minio_endpoint,
            access_key="minioadmin",
            secret_key="minioadmin123",
            secure=False
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def scrape_page(self, url):
        """À implémenter : scraper une page"""
        pass
    
    @abstractmethod
    def parse_job(self, html):
        """À implémenter : parser une offre"""
        pass
    
    def send_to_kafka(self, job_data, topic='job-offers-raw'):
        """Envoyer à Kafka"""
        self.kafka_producer.send(topic, job_data)
        self.logger.info(f"Job sent to Kafka: {job_data.get('job_id')}")
    
    def save_to_minio(self, job_id, html_content, bucket='scraped-jobs'):
        """Sauvegarder HTML dans MinIO"""
        from io import BytesIO
        data = BytesIO(html_content.encode('utf-8'))
        self.minio_client.put_object(
            bucket,
            f"{job_id}.html",
            data,
            length=len(html_content)
        )
        self.logger.info(f"HTML saved to MinIO: {job_id}")
```

#### 3.3 Scraper Indeed

Créer `kafka/producers/scrapers/indeed_scraper.py` :

```python
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseJobScraper
import time
import random

class IndeedScraper(BaseJobScraper):
    """Scraper pour Indeed France"""
    
    BASE_URL = "https://fr.indeed.com"
    
    def scrape_page(self, keyword, location, page=0):
        """Scraper une page de résultats"""
        url = f"{self.BASE_URL}/jobs"
        params = {
            'q': keyword,
            'l': location,
            'start': page * 10
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers)
        return response.text
    
    def parse_job(self, html):
        """Parser les offres d'une page"""
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        
        for job_card in soup.find_all('div', class_='job_seen_beacon'):
            try:
                job_data = {
                    'job_id': job_card.get('data-jk', ''),
                    'title': job_card.find('h2').text.strip(),
                    'company': job_card.find('span', class_='companyName').text.strip(),
                    'location': job_card.find('div', class_='companyLocation').text.strip(),
                    'source': 'indeed',
                    'scraped_at': time.time()
                }
                jobs.append(job_data)
            except Exception as e:
                self.logger.error(f"Error parsing job: {e}")
        
        return jobs
    
    def scrape(self, keyword, location, max_pages=5):
        """Scraper plusieurs pages"""
        all_jobs = []
        
        for page in range(max_pages):
            self.logger.info(f"Scraping page {page+1}/{max_pages}")
            
            # Scrape
            html = self.scrape_page(keyword, location, page)
            jobs = self.parse_job(html)
            
            # Envoyer à Kafka et MinIO
            for job in jobs:
                self.send_to_kafka(job)
                self.save_to_minio(job['job_id'], html)
                all_jobs.append(job)
            
            # Rate limiting
            time.sleep(random.uniform(2, 5))
        
        return all_jobs
```

#### 3.4 Utilisation

Créer `kafka/producers/run_scraper.py` :

```python
from scrapers.indeed_scraper import IndeedScraper
import os

if __name__ == '__main__':
    scraper = IndeedScraper(
        kafka_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092'),
        minio_endpoint=os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
    )
    
    jobs = scraper.scrape(
        keyword='data engineer',
        location='paris',
        max_pages=5
    )
    
    print(f"✅ {len(jobs)} offres scrapées")
```

**Checklist** :
- [ ] Base scraper créé
- [ ] Indeed scraper implémenté
- [ ] Tests locaux réussis
- [ ] Données dans Kafka
- [ ] HTML dans MinIO

**Prochains scrapers à implémenter** :
- [ ] LinkedIn (`linkedin_scraper.py`)
- [ ] Welcome to the Jungle (`wttj_scraper.py`)
- [ ] Apec (`apec_scraper.py`)

### Phase 4 : Jobs Spark (3-5 jours)

#### 4.1 Parser les offres (Spark Streaming)

Créer `spark/streaming/consume_jobs.py` :

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

spark = SparkSession.builder \
    .appName("ConsumeJobs") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .getOrCreate()

# Lire depuis Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "job-offers-raw") \
    .load()

# Parser le JSON
schema = StructType([
    StructField("job_id", StringType()),
    StructField("title", StringType()),
    StructField("company", StringType()),
    StructField("location", StringType()),
    StructField("source", StringType()),
    StructField("scraped_at", DoubleType())
])

parsed_df = df.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select("data.*")

# Ajouter des transformations
clean_df = parsed_df \
    .withColumn("scraped_date", from_unixtime("scraped_at").cast("date")) \
    .withColumn("title_clean", lower(col("title")))

# Écrire dans MinIO (Parquet)
query = clean_df.writeStream \
    .format("parquet") \
    .option("path", "s3a://processed-data/jobs/") \
    .option("checkpointLocation", "s3a://processed-data/checkpoints/jobs/") \
    .partitionBy("scraped_date", "source") \
    .outputMode("append") \
    .start()

query.awaitTermination()
```

#### 4.2 Extraction NLP

Créer `spark/batch/extract_skills.py` :

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf
from pyspark.sql.types import ArrayType, StringType
import spacy

# Charger modèle spaCy
nlp = spacy.load("fr_core_news_md")

def extract_skills(text):
    """Extraire les compétences techniques"""
    if not text:
        return []
    
    doc = nlp(text)
    skills = []
    
    # Liste de compétences techniques (à enrichir)
    tech_skills = {
        'python', 'java', 'spark', 'kafka', 'sql', 'hadoop',
        'docker', 'kubernetes', 'aws', 'gcp', 'azure',
        'machine learning', 'data science', 'big data'
    }
    
    # Extraire les tokens qui matchent
    for token in doc:
        if token.text.lower() in tech_skills:
            skills.append(token.text)
    
    return list(set(skills))

# Créer UDF
extract_skills_udf = udf(extract_skills, ArrayType(StringType()))

# Utilisation
spark = SparkSession.builder.appName("ExtractSkills").getOrCreate()

df = spark.read.parquet("s3a://processed-data/jobs/")

df_with_skills = df.withColumn("skills", extract_skills_udf(col("description")))

df_with_skills.write \
    .mode("overwrite") \
    .parquet("s3a://processed-data/jobs_enriched/")
```

**Checklist** :
- [ ] Spark Streaming configuré
- [ ] Parser JSON → Parquet
- [ ] Extraction NLP fonctionnelle
- [ ] Déduplication
- [ ] Matching offres-CVs

### Phase 5 : Airflow DAGs (2-3 jours)

#### 5.1 DAG de scraping quotidien

Créer `airflow/dags/scraping_daily.py` :

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'bigdata',
    'depends_on_past': False,
    'start_date': datetime(2024, 11, 24),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'scraping_daily',
    default_args=default_args,
    description='Scraping quotidien des offres',
    schedule_interval='0 2 * * *',  # 2h du matin
    catchup=False
)

# Scraper Indeed
scrape_indeed = BashOperator(
    task_id='scrape_indeed',
    bash_command='python /opt/airflow/kafka/producers/run_scraper.py --site indeed',
    dag=dag
)

# Scraper LinkedIn
scrape_linkedin = BashOperator(
    task_id='scrape_linkedin',
    bash_command='python /opt/airflow/kafka/producers/run_scraper.py --site linkedin',
    dag=dag
)

# Traiter avec Spark
process_jobs = SparkSubmitOperator(
    task_id='process_jobs',
    application='/opt/airflow/spark/streaming/consume_jobs.py',
    conn_id='spark_default',
    dag=dag
)

# Charger dans BigQuery
load_to_bq = BashOperator(
    task_id='load_to_bigquery',
    bash_command='python /opt/airflow/scripts/load_to_bigquery.py',
    dag=dag
)

# Définir l'ordre
[scrape_indeed, scrape_linkedin] >> process_jobs >> load_to_bq
```

**Checklist** :
- [ ] DAG de scraping créé
- [ ] DAG de processing créé
- [ ] DAG de loading vers BigQuery créé
- [ ] Tests sur Airflow UI

### Phase 6 : Dashboards Superset (2 jours)

#### 6.1 Connecter BigQuery

1. Ouvrir http://localhost:8088
2. Settings → Database Connections
3. Add Database
4. Choisir BigQuery
5. Config :
   ```
   bigquery://job-matching-bigdata/job_matching_dw?credentials_path=/app/gcp-service-account.json
   ```

#### 6.2 Créer les datasets

- Dataset 1 : `fact_job_offers`
- Dataset 2 : `fact_candidates`
- Dataset 3 : `agg_matching_scores`

#### 6.3 Créer les dashboards

**Dashboard 1 : Marché de l'Emploi**
- Chart 1 : Offres par jour (Line chart)
- Chart 2 : Top 10 compétences (Bar chart)
- Chart 3 : Carte géographique (Map)
- Chart 4 : Salaires moyens (Box plot)

**Dashboard 2 : Analyse Candidats**
- Chart 1 : Distribution expérience (Histogram)
- Chart 2 : Compétences recherchées (Word cloud)
- Chart 3 : Matching scores (Scatter plot)

**Checklist** :
- [ ] Connexion BigQuery configurée
- [ ] Datasets créés
- [ ] 2+ dashboards fonctionnels
- [ ] Rapports planifiés

### Phase 7 : Tests et Documentation (1-2 jours)

- [ ] Tests end-to-end
- [ ] Documentation des scrapers
- [ ] Documentation des jobs Spark
- [ ] Documentation des DAGs
- [ ] Tutoriels vidéo (optionnel)

## 📊 Estimation Totale

| Phase | Durée | Priorité |
|-------|-------|----------|
| 1. Démarrage et tests | 1-2 jours | 🔴 Critique |
| 2. BigQuery | 1 jour | 🔴 Critique |
| 3. Scrapers | 3-5 jours | 🟠 Haute |
| 4. Jobs Spark | 3-5 jours | 🟠 Haute |
| 5. DAGs Airflow | 2-3 jours | 🟡 Moyenne |
| 6. Dashboards | 2 jours | 🟡 Moyenne |
| 7. Tests | 1-2 jours | 🟢 Basse |
| **TOTAL** | **13-20 jours** | |

## 🎯 Objectifs par Semaine

### Semaine 1 (Jours 1-5)
- ✅ Infrastructure démarrée
- ✅ BigQuery configuré
- ✅ Premier scraper fonctionnel
- ✅ Données dans Kafka + MinIO

### Semaine 2 (Jours 6-10)
- ✅ Tous les scrapers implémentés
- ✅ Jobs Spark de parsing
- ✅ Extraction NLP basique
- ✅ Données dans BigQuery

### Semaine 3 (Jours 11-15)
- ✅ DAGs Airflow complets
- ✅ Pipeline automatisé
- ✅ Dashboards Superset
- ✅ Documentation

### Semaine 4 (Jours 16-20)
- ✅ Tests et optimisations
- ✅ Présentation
- ✅ Livrables finaux

## 📞 Support

**Besoin d'aide ?**
- Documentation : `docs/`
- Exemples : `notebooks/exploration/`
- Logs : `docker logs [service]`

**Ressources utiles** :
- Scrapy Tutorial : https://docs.scrapy.org/en/latest/intro/tutorial.html
- Spark Streaming : https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html
- Airflow : https://airflow.apache.org/docs/apache-airflow/stable/tutorial.html

---

**🚀 Bon courage ! Vous avez tout ce qu'il faut pour réussir !**

