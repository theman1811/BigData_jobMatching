# 🏗️ Architecture Détaillée - BigData OrangeScrum

## Vue d'ensemble

Ce document décrit l'architecture complète de la plateforme Big Data mise en place pour le projet OrangeScrum.

## 🎯 Objectifs

- **Ingestion** : Collecter des événements en temps réel via Kafka
- **Stockage** : Stocker les données brutes dans un Data Lake (GCS) et structurées dans un Data Warehouse (BigQuery)
- **Traitement** : Transformer les données avec Apache Spark (batch et streaming)
- **Orchestration** : Automatiser les pipelines avec Apache Airflow
- **Visualisation** : Créer des dashboards BI avec Looker Studio

## 📐 Architecture Technique

```
┌─────────────────────────────────────────────────────────────┐
│                    SOURCES DE DONNÉES                        │
│  (Applications, APIs, Fichiers, Bases de données, etc.)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  COUCHE D'INGESTION (Local)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │   KAFKA      │  │ SCHEMA REGISTRY │  │ KAFKA CONNECT  │ │
│  │ (Streaming)  │  │  (Validation)   │  │  (Connecteurs) │ │
│  └──────────────┘  └─────────────────┘  └────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               COUCHE DE TRAITEMENT (Local)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐ │
│  │              APACHE SPARK CLUSTER                      │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │ │
│  │  │  Master  │  │ Worker 1 │  │ Worker 2 │            │ │
│  │  └──────────┘  └──────────┘  └──────────┘            │ │
│  │                                                        │ │
│  │  • Spark Streaming (Temps réel)                       │ │
│  │  • Spark Batch (Traitements lourds)                   │ │
│  │  • PySpark (Transformations)                          │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                COUCHE DE STOCKAGE (GCP)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌──────────────────────────┐  │
│  │   DATA LAKE (GCS)    │    │  DATA WAREHOUSE          │  │
│  │                      │    │  (BIGQUERY)              │  │
│  │  • Données brutes    │───▶│                          │  │
│  │  • Parquet/Avro      │    │  • Données structurées   │  │
│  │  • Partitionnées     │    │  • Modèles BI            │  │
│  │  • 5 GB (Free Tier)  │    │  • Agrégations           │  │
│  └──────────────────────┘    └──────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                COUCHE DE VISUALISATION                       │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐ │
│  │              LOOKER STUDIO (Gratuit)                   │ │
│  │                                                        │ │
│  │  • Dashboards interactifs                             │ │
│  │  • Connexion directe à BigQuery                       │ │
│  │  • Rapports planifiés                                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              COUCHE D'ORCHESTRATION (Local)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐ │
│  │                 APACHE AIRFLOW                         │ │
│  │                                                        │ │
│  │  • Planification des jobs                             │ │
│  │  • Gestion des dépendances                            │ │
│  │  • Monitoring des pipelines                           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Composants Détaillés

### 1. Ingestion (Apache Kafka)

**Rôle** : Recevoir et distribuer les événements en temps réel

**Composants** :
- **Zookeeper** : Coordination du cluster Kafka
- **Kafka Broker** : Gestion des messages
- **Schema Registry** : Validation des schémas de données (Avro)
- **Kafka UI** : Interface de monitoring

**Configuration** :
- Port Kafka : 9092
- Port Schema Registry : 8081
- Port Kafka UI : 8080
- Topics auto-créés : activé
- Retention : 7 jours

### 2. Traitement (Apache Spark)

**Rôle** : Transformer et enrichir les données

**Composants** :
- **Spark Master** : Gestionnaire du cluster (port 7077)
- **Spark Worker 1 & 2** : Nœuds de calcul (2 cores, 2GB chacun)

**Capacités** :
- Spark Streaming : Traitement temps réel depuis Kafka
- Spark Batch : Traitements lourds planifiés
- PySpark : API Python pour les transformations

**Web UI** :
- Master : http://localhost:8082
- Worker 1 : http://localhost:8083
- Worker 2 : http://localhost:8084

### 3. Stockage (Google Cloud)

#### Data Lake (Google Cloud Storage)

**Rôle** : Stockage brut et économique des données

**Caractéristiques** :
- Format : Parquet (compression optimale)
- Organisation : Partitionnement par date
- Coût : 0€ (Free Tier 5 GB)

**Structure** :
```
gs://orangescrum-datalake/
├── raw/                    # Données brutes
│   ├── events/
│   │   └── date=2024-01-01/
│   ├── logs/
│   └── metrics/
├── processed/              # Données traitées
│   └── date=2024-01-01/
└── archive/                # Archives
```

#### Data Warehouse (BigQuery)

**Rôle** : Requêtes analytiques rapides

**Caractéristiques** :
- Dataset : orangescrum_dw
- Tables partitionnées par date
- Clustering sur colonnes fréquentes
- Coût : 0€ (Free Tier : 10 GB storage + 1 TB queries/mois)

**Schéma** :
```
orangescrum_dw/
├── raw_events              # Table brute
├── dim_users               # Dimension utilisateurs
├── dim_projects            # Dimension projets
├── fact_activities         # Fait activités
└── agg_daily_metrics       # Agrégations quotidiennes
```

### 4. Orchestration (Apache Airflow)

**Rôle** : Automatiser et planifier les pipelines

**Composants** :
- **Webserver** : Interface Web (port 8085)
- **Scheduler** : Planificateur de tâches
- **PostgreSQL** : Base de données métadonnées

**Credentials** :
- URL : http://localhost:8085
- Username : airflow
- Password : airflow

**DAGs types** :
1. **Ingestion quotidienne** : Charger données vers GCS
2. **Transformation batch** : Jobs Spark planifiés
3. **Chargement BigQuery** : Import depuis GCS
4. **Maintenance** : Nettoyage et archivage

### 5. Développement (Jupyter)

**Rôle** : Développement interactif PySpark

**Accès** :
- URL : http://localhost:8888
- Token : bigdata2024

**Packages installés** :
- PySpark 3.5.0
- Kafka clients
- Google Cloud SDK
- Pandas, NumPy, Matplotlib

## 🔄 Flux de Données

### Pipeline Temps Réel (Streaming)

```
1. Source → 2. Kafka → 3. Spark Streaming → 4. GCS → 5. BigQuery → 6. Looker Studio
   (App)    (Topic)     (Transformation)      (Raw)   (Warehouse)    (Dashboard)
```

**Exemple : Événements utilisateurs**
```python
1. Application génère événement → events-raw
2. Spark Streaming consomme events-raw
3. Transformation et enrichissement
4. Écriture dans GCS (Parquet)
5. Chargement dans BigQuery (batch 15 min)
6. Dashboard se met à jour
```

### Pipeline Batch (Planifié)

```
1. Airflow → 2. Spark Batch → 3. GCS → 4. BigQuery → 5. Looker Studio
   (DAG)       (Job)           (Parquet) (Table)       (Rapport)
```

**Exemple : Agrégations quotidiennes**
```python
1. Airflow DAG se déclenche à 2h du matin
2. Spark lit données de la veille depuis GCS
3. Calcule métriques agrégées
4. Écrit résultats dans BigQuery
5. Email de confirmation envoyé
```

## 💾 Stratégie de Données

### Modélisation

**Approche** : Modèle en étoile (Star Schema)

```
        ┌──────────────┐
        │  dim_users   │
        └──────┬───────┘
               │
        ┌──────▼─────────────────┐
        │                        │
  ┌─────┴────────┐      ┌───────┴────────┐
  │ dim_projects │◀─────┤ fact_activities│
  └──────────────┘      └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │   dim_dates    │
                        └────────────────┘
```

### Partitionnement

**GCS** : Partitionnement par date (Hive style)
```
/data/events/year=2024/month=01/day=15/
```

**BigQuery** : Partitionnement sur colonne date
```sql
CREATE TABLE events
PARTITION BY DATE(event_timestamp)
CLUSTER BY user_id, event_type
```

### Formats de Données

| Couche | Format | Raison |
|--------|--------|--------|
| Ingestion | Avro | Schéma intégré, évolution |
| Lake (Raw) | Parquet | Compression, columnar |
| Lake (Processed) | Parquet | Performance, taille |
| Warehouse | BigQuery native | Optimisé pour requêtes |

## 🔐 Sécurité

### Authentification

- **Airflow** : Basic Auth (user/password)
- **GCP** : Service Account avec clé JSON
- **Kafka** : PLAINTEXT (local), SSL en production

### Autorisation

**BigQuery** :
- Service Account avec rôle minimal (BigQuery Data Editor)
- Row-level security sur tables sensibles

**GCS** :
- Bucket privé (pas d'accès public)
- IAM roles spécifiques par service

### Secrets Management

**Local** : Variables d'environnement (.env)
**Production** : Google Secret Manager

## 📊 Monitoring

### Métriques à Surveiller

1. **Kafka** :
   - Lag des consumers
   - Throughput (messages/sec)
   - Taille des partitions

2. **Spark** :
   - Durée des jobs
   - Mémoire utilisée
   - Tasks échouées

3. **Airflow** :
   - DAGs en échec
   - Durée d'exécution
   - SLA respectés

4. **GCP** :
   - Coûts quotidiens
   - Quotas utilisés
   - Requêtes BigQuery

### Outils de Monitoring

- **Kafka UI** : Monitoring Kafka
- **Spark Web UI** : Jobs en cours
- **Airflow UI** : État des DAGs
- **GCP Console** : Facturation et quotas

## 🚀 Évolutions Futures

### Phase 2 (Optionnel)

1. **Data Quality** : Intégration de Great Expectations
2. **Data Catalog** : Ajout de DataHub ou Dataplex
3. **ML** : Modèles dans BigQuery ML
4. **Streaming avancé** : Pub/Sub + Dataflow

### Scalabilité

**Si volumes augmentent** :
- Passer à Dataproc pour Spark (auto-scaling)
- Utiliser Pub/Sub au lieu de Kafka local
- Activer crédits GCP étudiants (300$)

## 📚 Références

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Spark Documentation](https://spark.apache.org/docs/latest/)
- [Airflow Documentation](https://airflow.apache.org/docs/)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices)
- [Looker Studio Documentation](https://support.google.com/looker-studio)

