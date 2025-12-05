# 🚀 BigData Job Matching - Architecture Big Data Scalable

## 📋 Description

Plateforme Big Data scalable pour l'ingestion, la centralisation et l'analyse de données provenant des offres d'emploi et CVs de candidats sur internet.

**Mode : Hybride** (Développement local + GCP BigQuery)

## 🏗️ Architecture Modernisée

```
┌─────────────────────────────────────────────────────────┐
│ COUCHE DE SCRAPING (Web Scraping)                       │
├─────────────────────────────────────────────────────────┤
│  [Scrapers] → Indeed, LinkedIn, WTTJ, Apec             │
│  • Scrapy/Selenium pour extraction                      │
│  • Anti-ban & Rate limiting                             │
│  • Rotation User-Agent                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│ DÉVELOPPEMENT LOCAL (Docker Compose)                    │
├─────────────────────────────────────────────────────────┤
│  [Kafka KRaft] → [Spark] → [Airflow] → [Jupyter]       │
│   Ingestion      Process   Orchestration  Development   │
│                                                          │
│  [MinIO S3] ← Data Lake (stockage local)                │
│  [Superset] ← BI Dashboards (local)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│ CLOUD GCP (Free Tier)                                   │
├─────────────────────────────────────────────────────────┤
│  [BigQuery] → Data Warehouse + Analytics                │
│  • 10 GB stockage gratuit                               │
│  • 1 TB queries/mois gratuit                            │
└─────────────────────────────────────────────────────────┘
```

## 🛠️ Stack Technique

### Local (Docker)
- **Apache Kafka (KRaft)** : Ingestion temps réel (sans Zookeeper!)
- **Schema Registry** : Gestion des schémas Kafka
- **MinIO** : Data Lake S3-compatible (local, illimité)
- **Apache Spark** : Traitement distribué (PySpark)
- **Apache Airflow** : Orchestration des pipelines
- **Apache Superset** : BI & Dashboards (open-source)
- **Jupyter Notebook** : Développement et expérimentation
- **PostgreSQL** : Base de données (Airflow + Superset)
- **Redis** : Cache (Airflow + Superset)

### Scraping
- **Scrapy** : Framework de scraping
- **Selenium/Playwright** : Browser automation (sites JavaScript)
- **BeautifulSoup** : Parsing HTML
- **spaCy** : NLP pour extraction d'informations
- **pdfplumber** : Parsing de CVs PDF

### Cloud (GCP Free Tier)
- **BigQuery** : Data Warehouse (10 GB + 1 TB queries/mois gratuit)

## 📦 Prérequis

- Docker Desktop (ou Docker Engine + Docker Compose)
- Python 3.11+
- Compte Google Cloud Platform (uniquement pour BigQuery)
- 10 GB RAM minimum (12 GB recommandé)
- 20 GB espace disque

## 🚀 Démarrage Rapide

### 1. Cloner et configurer

```bash
# Copier le fichier de configuration
cp .env.example .env

# Éditer .env et configurer vos paramètres (notamment GCP si besoin)
nano .env
```

### 2. Démarrer tous les services

```bash
# Rendre les scripts exécutables
chmod +x start.sh stop.sh status.sh clean.sh

# Démarrer la plateforme
./start.sh
```

⏳ **Attendre 3-4 minutes** que tous les services démarrent.

### 3. Vérifier le statut

```bash
./status.sh
```

## 🌐 Accéder aux Interfaces Web

| Service | URL | Credentials |
|---------|-----|-------------|
| **Kafka UI** | http://localhost:8080 | Aucun |
| **MinIO Console** | http://localhost:9001 | user: `minioadmin`<br>pass: `minioadmin123` |
| **Spark Master** | http://localhost:8082 | Aucun |
| **Spark Worker 1** | http://localhost:8083 | Aucun |
| **Spark Worker 2** | http://localhost:8084 | Aucun |
| **Airflow** | http://localhost:8085 | user: `airflow`<br>pass: `airflow` |
| **Superset** | http://localhost:8088 | user: `admin`<br>pass: `admin` |
| **Jupyter** | http://localhost:8888 | token: `bigdata2024` |

## 📊 Phase 6 - Superset (BigQuery)

0) Se connecter à GCP via Docker (service account) :
```bash
docker run --platform=linux/amd64 --rm \
  -v "$PWD":/work \
  -v "$PWD/credentials/gcp-service-account.json":/sa.json \
  -w /work google/cloud-sdk:alpine \
  sh -c 'gcloud auth activate-service-account --key-file=/sa.json --project=<PROJECT_ID> && echo "GCP auth OK"'
```

1) Créer les vues BigQuery dédiées aux dashboards :
```bash
bq query --use_legacy_sql=false < bigquery/queries/superset_views.sql
```

2) Ajouter la connexion BigQuery dans Superset (UI)  
`bigquery://<project_id>/?credentials_path=/opt/airflow/credentials/bq-service-account.json`

3) Publier ces datasets dans Superset :
- `jobmatching_dw.v_offres_daily` (date, source, secteur, localisation, contrat, salaires)
- `jobmatching_dw.v_top_competences` (competences, secteur, localisation, source, date)
- `jobmatching_dw.v_salaires_secteur_ville` (moyennes + p50 par secteur/ville)
- `jobmatching_dw.v_geo_offres` (lat/long pour cartes)

4) Dashboards recommandés (ordre de livraison) :
- Marché de l’Emploi : courbe offres/jour, top compétences, carte, salaires
- Tendances Salariales : évolution, comparaisons villes, salaire vs expérience (si dispo)
- Analyse Compétences : émergentes, combinaisons, demande par secteur
- Matching (quand prêt) : scores, meilleures recommandations

5) Performance/UX :
- Cache Superset activé (Redis) ; ajuster TTL si besoin
- Colonnes date marquées dans chaque dataset pour le time grain
- Filtres globaux conseillés : date, source, secteur, localisation

## 📁 Structure du Projet

```
bigData_jobMatching/
│
├── docker-compose.yml         # Orchestration des services
│
├── docker/                    # Configurations Docker
│   ├── postgres/             # Init scripts PostgreSQL
│   └── scrapers/             # Scraper container
│       ├── Dockerfile
│       ├── requirements.txt
│       └── scraper_daemon.py
│
├── config/                    # Fichiers de configuration
│   ├── spark-defaults.conf   # Configuration Spark
│   └── superset_config.py    # Configuration Superset
│
├── data/                      # Données locales
│   ├── raw/                  # Données brutes
│   ├── processed/            # Données traitées
│   └── scraped/              # Pages scrapées
│
├── kafka/                     # Configuration Kafka
│   ├── producers/            # Producteurs (scrapers)
│   ├── consumers/            # Consommateurs
│   └── schemas/              # Schémas Avro
│
├── spark/                     # Jobs Spark
│   ├── streaming/            # Spark Streaming
│   ├── batch/                # Batch processing
│   └── nlp/                  # Traitement NLP
│
├── airflow/                   # DAGs Airflow
│   ├── dags/                 # Définitions des DAGs
│   ├── plugins/              # Plugins personnalisés
│   └── logs/                 # Logs
│
├── bigquery/                  # SQL BigQuery
│   ├── schemas/              # Schémas de tables
│   └── queries/              # Requêtes SQL
│
├── notebooks/                 # Jupyter notebooks
│   └── exploration/          # Notebooks d'exploration
│
├── scripts/                   # Scripts utilitaires
│   ├── setup/                # Scripts d'installation
│   └── gcp/                  # Scripts GCP
│
└── docs/                      # Documentation
    ├── architecture.md       # Architecture détaillée
    └── setup_gcp.md          # Guide configuration GCP
```

## 🔄 Flux de Données

### Pipeline Scraping → BigQuery

```
1. SCRAPING
   Scrapers → Kafka (job-offers-raw, cvs-raw)
   
2. STOCKAGE RAW
   Kafka → MinIO (HTML/PDF bruts)
   
3. TRAITEMENT
   Spark Streaming consomme Kafka
   → Parsing HTML/PDF
   → Extraction NLP (compétences, salaires, localisations)
   → Déduplication
   
4. STOCKAGE TRAITÉ
   Spark → MinIO (Parquet structuré)
   
5. DATA WAREHOUSE
   Airflow → Chargement MinIO vers BigQuery
   
6. VISUALISATION
   Superset → Connexion BigQuery
   → Dashboards interactifs
```

## 🎯 Cas d'Usage

### 1. Analyse du Marché de l'Emploi
- Tendances des offres d'emploi par secteur
- Salaires moyens par compétence et localisation
- Compétences les plus demandées
- Évolution temporelle du marché

### 2. Matching Offres-CVs
- Score de compatibilité candidat-offre
- Recommandations personnalisées
- Gap analysis de compétences
- Prédiction de salaire

### 3. Intelligence Économique
- Stratégies de recrutement des entreprises
- Émergence de nouvelles technologies
- Cartographie des bassins d'emploi
- Prévisions du marché

## 📊 Avantages de la Nouvelle Architecture

### ✅ Kafka KRaft (vs Zookeeper)
- **-1 conteneur** : Architecture simplifiée
- **Plus rapide** : Meilleures performances
- **Plus moderne** : Standard depuis Kafka 3.3+
- **Moins de RAM** : ~500 MB économisés

### ✅ MinIO (vs GCS)
- **100% local** : Pas de dépendance cloud pour le dev
- **Illimité** : Limité seulement par votre disque
- **API S3** : Compatible avec tous les outils AWS
- **0€** : Gratuit pour toujours

### ✅ Superset (vs Looker Studio)
- **Open-source** : Contrôle total
- **Plus puissant** : Nombreuses fonctionnalités BI
- **Local** : Pas besoin de compte Google
- **Extensible** : Plugins et customisation

## 💰 Coût Estimé

**Développement local** : 0 €  
**MinIO (Data Lake)** : 0 €  
**Superset (BI)** : 0 €  
**BigQuery (Free Tier)** : 0 € (10 GB + 1 TB queries/mois)  
**Total** : 0 € ✅

Avec les crédits étudiants GCP (300$), vous avez une marge confortable !

## 🔧 Configuration BigQuery

### 1. Créer un projet GCP

```bash
# Aller sur https://console.cloud.google.com
# Créer un nouveau projet
```

### 2. Activer BigQuery API

```bash
gcloud services enable bigquery.googleapis.com
```

### 3. Créer un Service Account

```bash
# Créer le service account
gcloud iam service-accounts create bigdata-sa \
  --display-name="BigData Service Account"

# Donner les permissions BigQuery
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:bigdata-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Créer la clé JSON
gcloud iam service-accounts keys create ./config/gcp-service-account.json \
  --iam-account=bigdata-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 4. Configurer le .env

```bash
# Éditer .env
GCP_PROJECT_ID=your-project-id
GCP_DATASET_ID=job_matching_dw
```

## 🧪 Tests Rapides

### Tester Kafka

```bash
# Créer un topic
docker exec -it bigdata_kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic test-topic

# Lister les topics
docker exec -it bigdata_kafka kafka-topics --list \
  --bootstrap-server localhost:9092
```

### Tester MinIO

```bash
# Ouvrir http://localhost:9001
# Login: minioadmin / minioadmin123
# Vérifier que les buckets sont créés
```

### Tester Spark + MinIO

```python
# Dans Jupyter (http://localhost:8888)
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("TestMinIO") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

# Créer un DataFrame
df = spark.createDataFrame([(1, "test")], ["id", "value"])

# Écrire dans MinIO
df.write.parquet("s3a://datalake/test/data.parquet")

print("✅ Test réussi!")
```

## 🛑 Arrêter la Plateforme

```bash
./stop.sh
```

## 🧹 Nettoyer Complètement

⚠️ **Attention** : Supprime toutes les données !

```bash
./clean.sh
```

## 📚 Documentation Complète

- **docs/architecture.md** : Architecture technique détaillée
- **docs/setup_gcp.md** : Guide complet GCP
- **COMMANDS.md** : Commandes utiles
- **QUICKSTART.md** : Guide de démarrage rapide

## 🆘 Problèmes Courants

### Port déjà utilisé

```bash
# Trouver le processus
lsof -i :8080

# Modifier le port dans docker-compose.yml
```

### Kafka ne démarre pas

```bash
# Vérifier les logs
docker logs bigdata_kafka

# Supprimer les volumes et redémarrer
./clean.sh
./start.sh
```

### MinIO inaccessible

```bash
# Vérifier le conteneur
docker logs bigdata_minio

# Vérifier que le port 9001 est libre
lsof -i :9001
```

## 📈 Roadmap

### Phase 1 : Infrastructure ✅
- [x] Docker Compose
- [x] Kafka KRaft
- [x] MinIO
- [x] Spark
- [x] Airflow
- [x] Superset

### Phase 2 : Scraping (en cours)
- [ ] Scraper Indeed
- [ ] Scraper LinkedIn
- [ ] Scraper Welcome to the Jungle
- [ ] Scraper Apec
- [ ] Anti-ban logic

### Phase 3 : Traitement
- [ ] Jobs Spark Streaming
- [ ] Parsing HTML → JSON
- [ ] Extraction NLP
- [ ] Déduplication
- [ ] Chargement BigQuery

### Phase 4 : BI
- [ ] Dashboards Superset
- [ ] Analyse marché emploi
- [ ] Matching offres-CVs
- [ ] Prédictions ML

## 👥 Équipe

Projet académique - Big Data & BI  
Technologies : Kafka, Spark, Airflow, MinIO, Superset, BigQuery

## 📄 Licence

Projet académique - Usage éducatif uniquement

---

**Stack 100% Open-Source | Développement 100% Local | Cloud Hybride** 🚀
