# ⚡ Guide de Démarrage Rapide - Architecture Modernisée

## 🎯 Qu'est-ce qui a changé ?

### Avant ❌
- Zookeeper + Kafka
- Google Cloud Storage (nécessite compte GCP)
- Looker Studio (nécessite compte Google)

### Maintenant ✅
- Kafka KRaft (sans Zookeeper!)
- MinIO (Data Lake local S3-compatible)
- Apache Superset (BI open-source)
- Couche de scraping intégrée

## 🚀 Démarrage en 4 Étapes

### Étape 1 : Préparer l'environnement

```bash
# Cloner le projet (si pas déjà fait)
cd bigData_orangeScrum

# Copier le fichier de configuration
cp .env.example .env

# Optionnel : Éditer .env pour personnaliser
nano .env
```

### Étape 2 : Démarrer tous les services

```bash
# Rendre les scripts exécutables
chmod +x start.sh stop.sh status.sh clean.sh

# Démarrer la plateforme complète
./start.sh
```

⏳ **Attendre 3-4 minutes** - C'est normal !

Les services démarrent dans cet ordre :
1. PostgreSQL & Redis
2. Kafka (KRaft)
3. MinIO + buckets
4. Spark Cluster
5. Airflow
6. Superset
7. Scrapers
8. Jupyter

### Étape 3 : Vérifier que tout fonctionne

```bash
# Afficher le statut de tous les services
./status.sh
```

Vous devriez voir ✅ pour tous les services.

### Étape 4 : Explorer les interfaces

Ouvrez votre navigateur sur ces URLs :

| Interface | URL | Login |
|-----------|-----|-------|
| **Kafka UI** | http://localhost:8080 | - |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin123 |
| **Spark** | http://localhost:8082 | - |
| **Airflow** | http://localhost:8085 | airflow / airflow |
| **Superset** | http://localhost:8088 | admin / admin |
| **Jupyter** | http://localhost:8888 | token: bigdata2024 |

## 🧪 Tests Rapides

### 1. Tester Kafka (KRaft mode - sans Zookeeper!)

```bash
# Créer un topic de test
docker exec -it bigdata_kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic test-topic \
  --partitions 3 \
  --replication-factor 1

# Lister les topics
docker exec -it bigdata_kafka kafka-topics --list \
  --bootstrap-server localhost:9092

# Produire des messages
docker exec -it bigdata_kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic test-topic
# (Tapez des messages puis Ctrl+C)

# Consommer les messages
docker exec -it bigdata_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic test-topic \
  --from-beginning
```

### 2. Tester MinIO (Data Lake S3)

Ouvrir http://localhost:9001 et vérifier que les buckets sont créés :
- ✅ datalake
- ✅ raw-data
- ✅ processed-data
- ✅ scraped-jobs
- ✅ scraped-cvs
- ✅ backups

### 3. Tester Spark + MinIO

Ouvrir Jupyter : http://localhost:8888 (token: bigdata2024)

Créer un nouveau notebook et exécuter :

```python
from pyspark.sql import SparkSession

# Créer session Spark avec MinIO
spark = SparkSession.builder \
    .appName("TestMinIO") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .master("spark://spark-master:7077") \
    .getOrCreate()

# Créer un DataFrame de test
data = [
    ("Data Engineer", "Paris", 50000),
    ("Data Scientist", "Lyon", 55000),
    ("ML Engineer", "Marseille", 60000)
]
columns = ["job_title", "location", "salary"]
df = spark.createDataFrame(data, columns)

# Afficher
df.show()

# Écrire dans MinIO
df.write.mode("overwrite").parquet("s3a://datalake/test/jobs.parquet")

print("✅ Données écrites dans MinIO!")

# Relire depuis MinIO
df_read = spark.read.parquet("s3a://datalake/test/jobs.parquet")
df_read.show()

print("✅ Données lues depuis MinIO!")

spark.stop()
```

### 4. Tester Superset

1. Ouvrir http://localhost:8088
2. Login : `admin` / `admin`
3. Cliquer sur "Settings" → "Database Connections"
4. Ajouter une connexion PostgreSQL :
   - Host : `postgres`
   - Port : `5432`
   - Database : `superset`
   - User : `airflow`
   - Password : `airflow`
5. Tester la connexion ✅

### 5. Tester un Scraper Simple

```bash
# Envoyer une commande au scraper daemon
docker exec -it bigdata_kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic scraper-commands

# Copier-coller ce JSON et appuyer sur Entrée :
{"scraper_type": "indeed", "params": {"keyword": "data engineer", "location": "paris"}}

# Vérifier le statut
docker exec -it bigdata_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic scraper-status \
  --from-beginning
```

## 📊 Exemple Complet : Pipeline End-to-End

Voici un exemple de pipeline complet de scraping → traitement → analyse :

### 1. Scraper des offres (Airflow)

Créer `airflow/dags/scraping_dag.py` :

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'bigdata',
    'depends_on_past': False,
    'start_date': datetime(2024, 11, 24),
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

scrape_indeed = BashOperator(
    task_id='scrape_indeed',
    bash_command='echo "Scraping Indeed..." && sleep 5',
    dag=dag
)

scrape_linkedin = BashOperator(
    task_id='scrape_linkedin',
    bash_command='echo "Scraping LinkedIn..." && sleep 5',
    dag=dag
)

scrape_indeed >> scrape_linkedin
```

### 2. Traiter avec Spark

Créer `spark/batch/process_jobs.py` :

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = SparkSession.builder \
    .appName("ProcessJobs") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .getOrCreate()

# Lire les données brutes
df = spark.read.json("s3a://scraped-jobs/2024-11-24/*.json")

# Nettoyage et transformation
df_clean = df \
    .dropDuplicates(["job_id"]) \
    .filter(col("salary").isNotNull()) \
    .withColumn("scraped_date", current_date())

# Sauvegarder en Parquet
df_clean.write \
    .mode("overwrite") \
    .partitionBy("scraped_date") \
    .parquet("s3a://processed-data/jobs/")

print(f"✅ {df_clean.count()} offres traitées")
```

### 3. Charger dans BigQuery (Airflow)

```python
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

load_to_bq = GCSToBigQueryOperator(
    task_id='load_to_bigquery',
    bucket='your-bucket',
    source_objects=['processed-data/jobs/*.parquet'],
    destination_project_dataset_table='job_matching_dw.fact_job_offers',
    source_format='PARQUET',
    write_disposition='WRITE_APPEND',
    dag=dag
)
```

### 4. Visualiser dans Superset

1. Aller sur Superset : http://localhost:8088
2. Créer une nouvelle connexion BigQuery
3. Créer un dataset sur `fact_job_offers`
4. Créer un dashboard avec :
   - Graphique : Salaires moyens par ville
   - Tableau : Top 10 compétences demandées
   - Carte : Répartition géographique des offres

## 🛑 Arrêter les Services

```bash
# Arrêter tous les conteneurs
./stop.sh

# Les données persistent dans les volumes Docker
```

## 🔄 Redémarrer

```bash
# Redémarrer (les données sont conservées)
./start.sh
```

## 🧹 Nettoyer Complètement

⚠️ **ATTENTION** : Supprime TOUTES les données !

```bash
# Arrêter et supprimer tout (conteneurs + volumes)
./clean.sh

# Puis redémarrer from scratch
./start.sh
```

## ❓ Problèmes Fréquents

### "Port already in use"

```bash
# Trouver le processus qui utilise le port
lsof -i :8080

# Tuer le processus ou changer le port dans docker-compose.yml
```

### Kafka ne démarre pas

```bash
# Vérifier les logs
docker logs bigdata_kafka

# Si erreur de format, supprimer le volume
docker volume rm bigdata_orangescrum_kafka_data
./start.sh
```

### MinIO inaccessible

```bash
# Vérifier les logs
docker logs bigdata_minio

# Vérifier les buckets
docker exec -it bigdata_minio mc ls myminio
```

### Spark ne voit pas MinIO

Vérifier que le fichier `config/spark-defaults.conf` existe et contient :

```properties
spark.hadoop.fs.s3a.endpoint              http://minio:9000
spark.hadoop.fs.s3a.access.key            minioadmin
spark.hadoop.fs.s3a.secret.key            minioadmin123
spark.hadoop.fs.s3a.path.style.access     true
```

### Superset ne démarre pas

```bash
# Initialiser manuellement
docker exec -it bigdata_superset superset db upgrade
docker exec -it bigdata_superset superset init
docker restart bigdata_superset
```

## 📚 Prochaines Étapes

Maintenant que votre plateforme fonctionne :

1. ✅ **Implémenter les scrapers** dans `kafka/producers/`
2. ✅ **Créer les jobs Spark** dans `spark/batch/` et `spark/streaming/`
3. ✅ **Créer les DAGs Airflow** dans `airflow/dags/`
4. ✅ **Configurer BigQuery** (voir `docs/setup_gcp.md`)
5. ✅ **Créer les dashboards Superset**

## 🆘 Besoin d'Aide ?

```bash
# Voir tous les logs
docker-compose logs -f

# Voir les logs d'un service spécifique
docker logs -f bigdata_kafka
docker logs -f bigdata_spark_master
docker logs -f bigdata_minio
```

---

**🎉 Bravo ! Votre plateforme Big Data est opérationnelle !**

**Stack** : Kafka KRaft | MinIO | Spark | Airflow | Superset | BigQuery  
**100% Open-Source | Développement Local | Cloud Hybride**

