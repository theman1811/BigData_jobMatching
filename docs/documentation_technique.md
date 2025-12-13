# 📚 Documentation Technique - BigData Job Matching

**Date de mise à jour** : Décembre 2024  
**Version** : 1.0

---

## 5.1. Architecture de la solution

### Présentation du système global

Plateforme Big Data hybride (local + cloud) pour l'ingestion, le traitement et l'analyse d'offres d'emploi et de CVs. Architecture modulaire avec orchestration automatisée via Apache Airflow.

### Schémas d'architecture

#### Architecture en couches

```
┌─────────────────────────────────────────────────────────────┐
│ COUCHE SCRAPING (Web Scraping)                              │
│ • Scrapers Python (Educarriere, Macarrierepro, Emploi.ci,   │
│   LinkedIn)                                                 │
│ • Container Docker dédié                                     │
│ • Anti-ban & Rate limiting                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ COUCHE INGESTION (Kafka KRaft)                              │
│ • Kafka Broker (KRaft mode, sans Zookeeper)                  │
│ • Schema Registry (validation Avro)                          │
│ • Kafka UI (monitoring)                                      │
│ Topics: job-offers-raw, job-offers-parsed, cvs-raw, etc.    │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│ MINIO (S3)      │         │ SPARK CLUSTER    │
│ Data Lake       │◄────────│ Processing       │
│ • scraped-jobs  │         │ • Master + 2     │
│ • processed-data│         │   Workers        │
│ • raw-data      │         │ • Batch +        │
│ • backups       │         │   Streaming      │
└─────────────────┘         └──────────────────┘
         │                           │
         └─────────────┬─────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ COUCHE ORCHESTRATION (Apache Airflow)                        │
│ • Webserver + Scheduler                                      │
│ • DAGs: scraping_daily, processing_spark, bigquery_load,     │
│   matching_pipeline                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ COUCHE DATA WAREHOUSE (BigQuery - GCP)                      │
│ • Dataset: jobmatching_dw                                    │
│ • Tables: Fact_OffresEmploi, Fact_CVs, Dim_*               │
│ • Vues Superset: v_offres_daily, v_top_competences, etc.   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ COUCHE VISUALISATION (Apache Superset)                       │
│ • Dashboards BI interactifs                                  │
│ • SQL Lab                                                    │
│ • Connexion BigQuery                                         │
└─────────────────────────────────────────────────────────────┘
```

#### Modules et interactions

1. **Module Scraping** (`kafka/producers/scrapers/`)
   - Scrapers héritant de `BaseJobScraperCI`
   - Publication Kafka + sauvegarde MinIO
   - Rotation User-Agent, délais aléatoires

2. **Module Ingestion** (`kafka/`)
   - Topics Kafka pour flux asynchrones
   - Schema Registry pour validation
   - Kafka UI pour monitoring

3. **Module Traitement** (`spark/batch/`, `spark/streaming/`)
   - **Batch** : parsing, extraction, enrichissement
   - **Streaming** : consommation temps réel depuis Kafka

4. **Module Orchestration** (`airflow/dags/`)
   - DAGs planifiés avec dépendances
   - Intégration Spark, BigQuery, Docker

5. **Module Stockage** (`bigquery/`, MinIO)
   - **MinIO** : données brutes et traitées (Parquet)
   - **BigQuery** : warehouse avec schéma en étoile

6. **Module Visualisation** (`config/superset_config.py`)
   - Superset connecté à BigQuery
   - Vues pré-agrégées pour dashboards

#### Flux de données

1. **Flux Scraping → Kafka → MinIO**
   ```
   Scrapers → job-offers-raw (Kafka) → MinIO (scraped-jobs/)
   ```

2. **Flux Kafka → Spark Streaming → MinIO**
   ```
   Kafka (job-offers-raw) → Spark Streaming → MinIO (processed-data/jobs/)
   ```

3. **Flux Batch Processing (Airflow)** ⚠️ **ACTUEL**
   ```
   MinIO (scraped-jobs/*.html) 
     → parse_jobs (lecture directe, BATCH_LIMIT=500)
     → extract_skills 
     → extract_salary 
     → extract_sectors 
     → MinIO (processed-data/)
   ```

4. **Flux Chargement BigQuery**
   ```
   MinIO (processed-data/) → load_to_bigquery → BigQuery (Fact_OffresEmploi)
   ```

5. **Flux Visualisation**
   ```
   BigQuery → Superset → Dashboards interactifs
   ```

---

## 5.2. Conception logique et technique

### Description des composants

#### 1. Scrapers (Classes Python)

**Classe abstraite** : `BaseJobScraperCI` (`kafka/producers/scrapers/base_scraper.py`)
```python
# Fonctionnalités principales:
- setup_kafka() : Connexion Kafka Producer
- setup_minio() : Connexion MinIO Client
- clean_location_ci() : Normalisation localisations ivoiriennes
- clean_salary_ci() : Parsing salaires FCFA
- _extract_skills_from_text() : Extraction basique compétences
- create_job_id() : Génération ID déterministe
```

**Scrapers concrets** :
- `EducarriereScraper` : Scraping Educarriere.ci
- `MacarriereproScraper` : Scraping Macarrierepro.com
- `EmploiCIScraper` : Scraping GoAfricaOnline (remplace Emploi.ci)
- `LinkedInScraper` : Scraping LinkedIn (optionnel, peut échouer)

#### 2. Jobs Spark Batch

**a) `parse_jobs.py` : Parsing HTML → JSON structuré**
```python
# Configuration actuelle:
- Lecture directe depuis s3a://scraped-jobs/*.html
- Pas d'étape de merge préalable (désactivée)
- BATCH_LIMIT=500 fichiers par exécution
- UDFs d'extraction:
  * extract_title_udf() : Titre depuis HTML
  * extract_company_udf() : Entreprise
  * extract_description_udf() : Description
  * extract_requirements_udf() : Exigences/compétences
  * extract_location_udf() : Localisation
  * extract_salary_udf() : Salaire
```

**b) `extract_skills.py` : Extraction NLP compétences**
```python
# Algorithme:
- Catalogue de compétences par catégorie (Python, Java, AWS, etc.)
- Recherche pattern-based dans texte
- Classification par catégorie
- spaCy pour NLP avancé (optionnel)
```

**c) `extract_salary.py` : Extraction salaires**
```python
# Patterns regex:
- Montants FCFA/CFA/XOF
- Montants EUR/$
- Période (mois/an/jour)
- Normalisation vers FCFA
```

**d) `extract_sectors.py` : Extraction secteurs d'activité**
```python
# Classification par secteur:
- Analyse texte description/titre
- Mapping vers secteurs standardisés
```

**e) `load_to_bigquery.py` : Chargement BigQuery**
```python
# Transformations:
- Génération IDs déterministes (entreprise_id, localisation_id)
- Mapping vers schéma BigQuery
- Partitionnement par date_publication
- Clustering par entreprise_id, localisation_id
```

**⚠️ Jobs désactivés** :
- `merge_html.py` : **DÉSACTIVÉ** - trop lent sur setup local
- `deduplicate.py` : **DÉSACTIVÉ** - données d'entrée trop génériques

#### 3. Pipeline de traitement actuel

```
scraped-jobs/*.html (lecture directe, BATCH_LIMIT=500)
    ↓
spark_parse_jobs (parse_jobs.py)
    ↓
spark_extract_skills (extract_skills.py)
    ↓
spark_extract_salary (extract_salary.py)
    ↓
spark_extract_sectors (extract_sectors.py)
    ↓
check_processing_quality
```

**Note** : Le merge HTML et la déduplication sont désactivés dans le pipeline actuel (trop lent pour le setup local selon les commentaires du code).

#### 4. Schéma BigQuery (Modèle en étoile)

**Tables Dimensions** :
```sql
- Dim_Entreprise (entreprise_id, nom_entreprise, secteur_id, taille_entreprise)
- Dim_Localisation (localisation_id, ville, region, departement, pays, lat/long)
- Dim_Competence (competence_id, nom_competence, categorie, niveau_demande)
- Dim_Secteur (secteur_id, nom_secteur, categorie_parent)
```

**Tables de Fait** :
```sql
- Fact_OffresEmploi (
    offre_id, titre_poste, entreprise_id, localisation_id, secteur_id,
    type_contrat, niveau_experience, teletravail, salaire_min/max,
    competences ARRAY<STRING>, competences_ids ARRAY<STRING>,
    source_site, date_publication, scraped_at
  )
  PARTITION BY date_publication
  CLUSTER BY entreprise_id, localisation_id, secteur_id

- Fact_CVs (
    cv_id, annees_experience, niveau_etudes, competences,
    localisation_souhaitee_id, secteur_souhaite_id, salaire_souhaite
  )
  PARTITION BY DATE(scraped_at)
```

**Tables Agrégées** :
```sql
- agg_matching_scores (job_id, candidate_id, match_score, skill_match_pct)
```

**Vues Superset** :
```sql
- v_offres_daily : Agrégations quotidiennes par source/secteur/localisation
- v_top_competences : Top compétences avec occurrences
- v_salaires_secteur_ville : Salaires moyens/médians par secteur/ville
- v_geo_offres : Données géographiques pour cartes
- v_salaires_secteur : Salaires par secteur avec percentiles
- v_teletravail_secteur : Analyse télétravail par secteur
```

#### 5. DAGs Airflow

**a) `scraping_daily_dag.py` (02:00 quotidien)**
```python
# Tâches parallèles:
- scrape_educarriere (DockerOperator)
- scrape_macarrierepro (DockerOperator)
- scrape_emploi_ci (DockerOperator)
- scrape_linkedin (DockerOperator, optionnel)
→ wait_all_scrapers → check_data_quality → notify_completion
```

**b) `processing_spark_dag.py` (04:00 quotidien)**
```python
# Pipeline séquentiel (sans merge ni déduplication):
spark_parse_jobs → spark_extract_skills 
→ spark_extract_salary → spark_extract_sectors 
→ check_processing_quality
```

**c) `bigquery_load_dag.py` (Quotidien)**
```python
# Tâches:
- check_offers_ready → load_job_offers (SparkSubmitOperator)
- check_cvs_ready → load_cvs_placeholder (EmptyOperator)
```

**d) `matching_pipeline_dag.py` (08:00 quotidien)**
```python
# Pipeline matching (à compléter):
check_matching_job → spark_matching → load_matching_results 
→ generate_recommendations
```

### Interfaces utilisateur / API

1. **Kafka UI** (`http://localhost:8080`)
   - Monitoring topics, consumers, messages
   - Pas d'authentification

2. **MinIO Console** (`http://localhost:9001`)
   - Gestion buckets, fichiers
   - Credentials: `minioadmin` / `minioadmin123`

3. **Spark Web UI**
   - Master: `http://localhost:8082`
   - Worker 1: `http://localhost:8083`
   - Worker 2: `http://localhost:8084`

4. **Airflow UI** (`http://localhost:8085`)
   - Monitoring DAGs, tâches, logs
   - Credentials: `airflow` / `airflow`

5. **Superset** (`http://localhost:8088`)
   - Dashboards, SQL Lab
   - Credentials: `admin` / `admin`

6. **Jupyter** (`http://localhost:8888`)
   - Notebooks PySpark
   - Token: `bigdata2024`

---

## 5.3. Mise en œuvre pratique

### Description des étapes de développement / intégration

#### Phase 1 : Configuration initiale

1. **Prérequis**
   ```bash
   - Docker Desktop installé
   - Python 3.11+
   - Compte GCP (pour BigQuery)
   - 10 GB RAM minimum
   ```

2. **Configuration GCP**
   ```bash
   # Créer Service Account
   gcloud iam service-accounts create bigdata-sa
   
   # Permissions BigQuery
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:bigdata-sa@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.dataEditor"
   
   # Télécharger clé JSON
   gcloud iam service-accounts keys create ./credentials/gcp-service-account.json \
     --iam-account=bigdata-sa@PROJECT_ID.iam.gserviceaccount.com
   ```

3. **Variables d'environnement**
   ```bash
   # Créer .env
   GCP_PROJECT_ID=your-project-id
   BIGQUERY_DATASET=jobmatching_dw
   ```

#### Phase 2 : Démarrage infrastructure

1. **Build images Docker**
   ```bash
   docker-compose build
   ```

2. **Démarrer services**
   ```bash
   ./start.sh
   # Ou: docker-compose up -d
   ```

3. **Vérification services**
   ```bash
   ./status.sh
   # Vérifier que tous les conteneurs sont "Up"
   ```

#### Phase 3 : Initialisation BigQuery

1. **Créer dataset**
   ```bash
   bq mk --dataset jobmatching_dw
   ```

2. **Créer tables**
   ```bash
   bq query --use_legacy_sql=false < bigquery/schemas/create_tables.sql
   ```

3. **Créer vues Superset**
   ```bash
   bq query --use_legacy_sql=false < bigquery/queries/superset_views.sql
   ```

#### Phase 4 : Configuration Superset

1. **Connexion BigQuery**
   - UI Superset → Databases → Add Database
   - Connection String: `bigquery://PROJECT_ID/?credentials_path=/opt/airflow/credentials/bq-service-account.json`

2. **Publier datasets**
   - Importer tables depuis BigQuery
   - Publier vues: `v_offres_daily`, `v_top_competences`, etc.

3. **Créer dashboards**
   - Marché de l'Emploi (offres/jour, top compétences, carte)
   - Tendances Salariales (évolution, comparaisons)
   - Analyse Compétences (émergentes, combinaisons)

#### Phase 5 : Tests et validation

1. **Test scraping manuel**
   ```bash
   docker exec -it bigdata_scrapers python /app/producers/run_scraper.py \
     --scraper educarriere --max-pages 2
   ```

2. **Vérification Kafka**
   ```bash
   # Kafka UI: http://localhost:8080
   # Vérifier messages dans job-offers-raw
   ```

3. **Test Spark job**
   ```bash
   # Via Airflow UI: déclencher DAG processing_spark manuellement
   # Ou via Jupyter: exécuter parse_jobs.py
   ```

4. **Vérification BigQuery**
   ```bash
   bq query --use_legacy_sql=false \
     "SELECT COUNT(*) FROM jobmatching_dw.Fact_OffresEmploi"
   ```

### Environnements de déploiement

#### Environnement local (Docker Compose)

**Services conteneurisés** (17 conteneurs) :
- Kafka (KRaft), Schema Registry, Kafka UI
- MinIO (Data Lake S3)
- Spark (Master + 2 Workers)
- Airflow (Webserver + Scheduler + Init)
- Superset (+ Init)
- PostgreSQL (Airflow + Superset)
- Redis (Cache)
- Jupyter
- Scrapers

**Volumes persistants** :
```yaml
- kafka_data
- minio_data
- spark_master_data, spark_worker_1_data, spark_worker_2_data
- postgres_data
- redis_data
- superset_home
```

**Réseau** : `bigdata_network` (bridge)

#### Environnement cloud (GCP)

**BigQuery (Free Tier)** :
- 10 GB stockage gratuit
- 1 TB requêtes/mois gratuit
- Dataset: `jobmatching_dw`
- Tables partitionnées et clusterisées

**Service Account** :
- Authentification via JSON key
- Permissions: `roles/bigquery.dataEditor`
- Monté dans conteneurs Airflow/Spark

#### Configuration hybride

**Local** :
- Scraping, Kafka, Spark, MinIO, Airflow, Superset
- Développement et tests

**Cloud** :
- BigQuery uniquement (warehouse)
- Visualisation Superset connectée à BigQuery

#### Scripts de gestion

```bash
./start.sh      # Démarre tous les services
./stop.sh       # Arrête tous les services
./status.sh     # Affiche statut des conteneurs
./clean.sh      # Supprime volumes (⚠️ perte de données)
```

#### Monitoring et logs

- **Kafka UI** : monitoring topics
- **Spark UI** : jobs en cours
- **Airflow UI** : état DAGs, logs tâches
- **MinIO Console** : fichiers stockés
- **Superset** : métriques dashboards
- **Logs Docker** : `docker logs <container_name>`

---

## Résumé technique

- **Architecture** : 6 couches (Scraping → Ingestion → Traitement → Stockage → Orchestration → Visualisation)
- **Technologies** : Kafka KRaft, Spark 3.5.1, Airflow 2.8.0, Superset, MinIO, BigQuery
- **Modèle de données** : Schéma en étoile (BigQuery) avec partitionnement et clustering
- **Orchestration** : 4 DAGs Airflow avec dépendances et planification
- **Pipeline actuel** : Parse → Extract Skills → Extract Salary → Extract Sectors (sans merge ni déduplication)
- **Déploiement** : Hybride (local Docker + cloud BigQuery)
- **Coût** : 0€ (Free Tier GCP suffisant pour développement)

Cette architecture permet un pipeline automatisé de bout en bout, du scraping à la visualisation, avec scalabilité et monitoring intégrés.

---

## Notes importantes

⚠️ **Jobs désactivés** :
- `merge_html.py` : Désactivé car trop lent sur setup local
- `deduplicate.py` : Désactivé car données d'entrée trop génériques

✅ **Pipeline actuel optimisé** :
- Lecture directe depuis `scraped-jobs/*.html`
- Limite de 500 fichiers par exécution (`BATCH_LIMIT`)
- Pas d'étape de merge préalable
- Pipeline simplifié pour performance locale
