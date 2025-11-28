# 🎮 Aide-Mémoire des Commandes

Guide de référence rapide pour toutes les commandes disponibles dans ce projet.

## 🚀 Gestion de la Plateforme

### Démarrage

```bash
# Démarrer tous les services
./start.sh

# Démarrer en mode détaché (sans logs)
docker-compose up -d

# Démarrer un service spécifique
docker-compose up -d kafka
docker-compose up -d spark-master
docker-compose up -d airflow-webserver
```

### Arrêt

```bash
# Arrêter tous les services
./stop.sh

# Arrêter et supprimer les volumes (⚠️ perte de données)
docker-compose down -v

# Arrêter un service spécifique
docker-compose stop kafka
```

### Statut

```bash
# Voir le statut de tous les services
./status.sh

# Voir les conteneurs en cours d'exécution
docker-compose ps

# Voir l'utilisation des ressources
docker stats
```

## 📋 Logs et Débogage

### Voir les Logs

```bash
# Logs de tous les services (temps réel)
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f kafka
docker-compose logs -f spark-master
docker-compose logs -f airflow-webserver

# Logs des 100 dernières lignes
docker-compose logs --tail=100 kafka

# Logs depuis une date
docker-compose logs --since 2024-01-01T00:00:00
```

### Entrer dans un Conteneur

```bash
# Kafka
docker exec -it bigdata_kafka bash

# Spark Master
docker exec -it bigdata_spark_master bash

# Airflow
docker exec -it bigdata_airflow_webserver bash

# Jupyter
docker exec -it bigdata_jupyter bash

# PostgreSQL
docker exec -it bigdata_postgres psql -U airflow
```

## 🔧 Kafka

### Topics

```bash
# Créer les topics par défaut
./scripts/setup/create_kafka_topics.sh

# Lister les topics
docker exec bigdata_kafka kafka-topics \
  --list \
  --bootstrap-server localhost:9092

# Créer un topic
docker exec bigdata_kafka kafka-topics \
  --create \
  --bootstrap-server localhost:9092 \
  --topic mon-topic \
  --partitions 3 \
  --replication-factor 1

# Décrire un topic
docker exec bigdata_kafka kafka-topics \
  --describe \
  --bootstrap-server localhost:9092 \
  --topic mon-topic

# Supprimer un topic
docker exec bigdata_kafka kafka-topics \
  --delete \
  --bootstrap-server localhost:9092 \
  --topic mon-topic
```

### Producteur / Consommateur

```bash
# Producteur en ligne de commande
docker exec -it bigdata_kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic mon-topic

# Consommateur en ligne de commande (depuis le début)
docker exec -it bigdata_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic mon-topic \
  --from-beginning

# Consommateur avec clé et valeur
docker exec -it bigdata_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic mon-topic \
  --property print.key=true \
  --property key.separator=: \
  --from-beginning

# Groupes de consommateurs
docker exec bigdata_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Détails d'un groupe
docker exec bigdata_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group mon-groupe \
  --describe
```

## ⚡ Spark

### Soumettre un Job

```bash
# Job PySpark local
docker exec bigdata_spark_master spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark-apps/mon_job.py

# Job avec arguments
docker exec bigdata_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.executor.memory=1g \
  --conf spark.executor.cores=1 \
  /opt/spark-apps/mon_job.py arg1 arg2

# Job avec dépendances
docker exec bigdata_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/mon_job_kafka.py
```

### PySpark Shell

```bash
# Lancer PySpark en interactif
docker exec -it bigdata_spark_master pyspark \
  --master spark://spark-master:7077

# Avec Kafka
docker exec -it bigdata_spark_master pyspark \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0
```

### Monitoring

```bash
# Ouvrir Spark Master UI
open http://localhost:8082

# Ouvrir Worker 1 UI
open http://localhost:8083

# Ouvrir Worker 2 UI
open http://localhost:8084

# Voir les jobs en cours (dans Jupyter)
open http://localhost:4040
```

## 🌊 Airflow

### DAGs

```bash
# Lister les DAGs
docker exec bigdata_airflow_scheduler airflow dags list

# Déclencher un DAG
docker exec bigdata_airflow_scheduler airflow dags trigger mon_dag

# Tester une tâche
docker exec bigdata_airflow_scheduler airflow tasks test mon_dag ma_tache 2024-01-01

# Voir l'état d'un DAG
docker exec bigdata_airflow_scheduler airflow dags state mon_dag 2024-01-01
```

### Base de Données

```bash
# Initialiser la BD (déjà fait au démarrage)
docker exec bigdata_airflow_webserver airflow db init

# Créer un utilisateur admin
docker exec bigdata_airflow_webserver airflow users create \
  --username admin \
  --firstname John \
  --lastname Doe \
  --role Admin \
  --email admin@example.com \
  --password admin

# Lister les utilisateurs
docker exec bigdata_airflow_webserver airflow users list
```

### Variables et Connections

```bash
# Définir une variable
docker exec bigdata_airflow_webserver airflow variables set ma_variable "valeur"

# Lister les variables
docker exec bigdata_airflow_webserver airflow variables list

# Créer une connexion
docker exec bigdata_airflow_webserver airflow connections add mon_conn \
  --conn-type postgres \
  --conn-host postgres \
  --conn-login airflow \
  --conn-password airflow \
  --conn-port 5432
```

## 📓 Jupyter

### Gestion

```bash
# Voir le token
docker exec bigdata_jupyter jupyter server list

# Installer un package Python
docker exec bigdata_jupyter pip install nom-du-package

# Lister les packages installés
docker exec bigdata_jupyter pip list
```

## 💾 PostgreSQL (Airflow)

```bash
# Se connecter à PostgreSQL
docker exec -it bigdata_postgres psql -U airflow -d airflow

# Depuis psql:
\dt              # Lister les tables
\d+ nom_table    # Décrire une table
\q               # Quitter

# Backup de la base
docker exec bigdata_postgres pg_dump -U airflow airflow > backup.sql

# Restore
docker exec -i bigdata_postgres psql -U airflow airflow < backup.sql
```

## ☁️ Google Cloud Platform

### Configuration

```bash
# Tester la connexion GCP
python3 scripts/gcp/test_connection.py

# Installer les dépendances GCP
pip install google-cloud-storage google-cloud-bigquery
```

### GCS (Cloud Storage)

```bash
# Lister les buckets
gsutil ls

# Lister les fichiers d'un bucket
gsutil ls gs://mon-bucket/

# Uploader un fichier
gsutil cp fichier.txt gs://mon-bucket/

# Télécharger un fichier
gsutil cp gs://mon-bucket/fichier.txt ./

# Copier un dossier
gsutil -m cp -r dossier/ gs://mon-bucket/

# Supprimer un fichier
gsutil rm gs://mon-bucket/fichier.txt

# Synchroniser un dossier
gsutil -m rsync -r dossier_local/ gs://mon-bucket/dossier_distant/
```

### BigQuery

```bash
# Lister les datasets
bq ls

# Lister les tables d'un dataset
bq ls orangescrum_dw

# Décrire une table
bq show orangescrum_dw.ma_table

# Exécuter une requête
bq query --use_legacy_sql=false \
  'SELECT * FROM `orangescrum_dw.ma_table` LIMIT 10'

# Charger des données depuis GCS
bq load \
  --source_format=PARQUET \
  orangescrum_dw.ma_table \
  gs://mon-bucket/data/*.parquet

# Exporter vers GCS
bq extract \
  --destination_format=PARQUET \
  orangescrum_dw.ma_table \
  gs://mon-bucket/export/*.parquet
```

## 🧪 Tests et Vérification

### Prérequis

```bash
# Vérifier les prérequis système
./scripts/setup/check_prerequisites.sh
```

### Tests de Connectivité

```bash
# Test Kafka
docker exec bigdata_kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092

# Test Spark
curl http://localhost:8082

# Test Airflow
curl http://localhost:8085/health

# Test Jupyter
curl http://localhost:8888

# Test GCP
python3 scripts/gcp/test_connection.py
```

### Healthchecks

```bash
# Voir les healthchecks de tous les services
docker ps --format "table {{.Names}}\t{{.Status}}"

# Healthcheck d'un service spécifique
docker inspect --format='{{.State.Health.Status}}' bigdata_kafka
```

## 🧹 Nettoyage

### Nettoyage Léger

```bash
# Supprimer les logs Airflow
rm -rf ./airflow/logs/*

# Supprimer les données de test
rm -rf ./data/raw/* ./data/processed/*
```

### Nettoyage Complet

```bash
# Nettoyer tout (⚠️ perte de données)
./clean.sh

# Ou manuellement
docker-compose down -v
docker system prune -a
```

## 📊 Monitoring

### Ressources Docker

```bash
# Utilisation en temps réel
docker stats

# Utilisation des volumes
docker system df -v

# Nettoyer les ressources inutilisées
docker system prune
```

### Ports Utilisés

```bash
# Vérifier qu'un port est libre
lsof -i :8080

# Lister tous les ports utilisés par Docker
docker-compose ps
```

## 🔄 Redémarrage

### Redémarrer un Service

```bash
# Redémarrer un service
docker-compose restart kafka

# Redémarrer tous les services
docker-compose restart

# Redémarrer avec reconstruction
docker-compose up -d --build
```

### Forcer une Reconstruction

```bash
# Reconstruire et redémarrer
docker-compose down
docker-compose up -d --build

# Reconstruire sans cache
docker-compose build --no-cache
docker-compose up -d
```

## 💡 Astuces Utiles

### Alias à Ajouter dans ~/.zshrc ou ~/.bashrc

```bash
# Ajouter ces alias pour gagner du temps
alias dc='docker-compose'
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down'
alias dcps='docker-compose ps'
alias dclogs='docker-compose logs -f'

# Kafka
alias kafka-topics='docker exec bigdata_kafka kafka-topics --bootstrap-server localhost:9092'
alias kafka-producer='docker exec -it bigdata_kafka kafka-console-producer --bootstrap-server localhost:9092'
alias kafka-consumer='docker exec -it bigdata_kafka kafka-console-consumer --bootstrap-server localhost:9092'

# Spark
alias spark-submit='docker exec bigdata_spark_master spark-submit --master spark://spark-master:7077'
alias pyspark='docker exec -it bigdata_spark_master pyspark --master spark://spark-master:7077'

# Airflow
alias airflow='docker exec bigdata_airflow_scheduler airflow'
```

### Surveiller les Logs en Temps Réel

```bash
# Terminal 1: Kafka
docker-compose logs -f kafka

# Terminal 2: Spark
docker-compose logs -f spark-master spark-worker-1

# Terminal 3: Airflow
docker-compose logs -f airflow-webserver airflow-scheduler
```

---

**Bon développement ! 🚀**

Pour plus d'informations, consultez :
- **README.md** : Vue d'ensemble
- **QUICKSTART.md** : Démarrage rapide
- **docs/architecture.md** : Architecture détaillée
- **docs/setup_gcp.md** : Configuration GCP

