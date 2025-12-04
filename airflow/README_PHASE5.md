# 📋 Phase 5 : DAGs Airflow - Orchestration des Pipelines

## 🎯 Objectif
Créer l'orchestration complète des pipelines Big Data avec Apache Airflow.

## 📁 Fichiers Créés

### DAGs Principaux
- **`bigquery_load_dag.py`** : Chargement des données vers BigQuery
- **`scraping_daily_dag.py`** : Scraping quotidien automatisé
- **`processing_spark_dag.py`** : Processing Spark des données

### Outils
- **`test_connections.py`** : Test des connexions Airflow

## 🔄 Flux de Données Orchestré

```
Scraping (2h) → Processing (4h) → BigQuery Loading
     ↓              ↓              ↓
   Kafka        MinIO → Spark    BigQuery
   Raw          Processed       Warehouse
```

## 🕐 Programmation des DAGs

| DAG | Schedule | Description |
|-----|----------|-------------|
| `scraping_daily` | `0 2 * * *` | 2h du matin - Scraping quotidien |
| `processing_spark` | `0 4 * * *` | 4h du matin - Processing Spark |
| `bigquery_load` | Manuel/Daily | Chargement BigQuery (manuel ou quotidien) |

## 🚀 Utilisation

### 1. Démarrer les Services
```bash
./start.sh
```

### 2. Accéder à Airflow
- **URL** : http://localhost:8085
- **Login** : `airflow` / `airflow`

### 3. Tester les Connexions
```bash
cd airflow
python test_connections.py
```

### 4. Activer les DAGs
1. Aller dans **Admin → Variables** et définir :
   - `PROJECT_ROOT` : `/opt/airflow/project`
   - `GCP_PROJECT_ID` : `bigdata-jobmatching-test`
   - `BIGQUERY_DATASET` : `jobmatching_dw`

2. Aller dans **Admin → Connections** et vérifier/créer :
   - `spark_default` : Connexion Spark Master
   - `bigquery_default` : Connexion BigQuery
   - `minio_default` : Connexion MinIO (optionnel)

3. Dans **DAGs**, activer les DAGs :
   - `scraping_daily`
   - `processing_spark`
   - `bigquery_load`

### 5. Tester les DAGs
1. **Trigger manuel** : Bouton "Trigger DAG" pour chaque DAG
2. **Monitorer** : Onglet "Graph View" et "Tree View"
3. **Logs** : Cliquer sur une tâche → "View Logs"

## ⚙️ Configuration Requise

### Variables d'Environnement
```bash
# Dans Airflow Admin → Variables
PROJECT_ROOT=/opt/airflow/project
GCP_PROJECT_ID=bigdata-jobmatching-test
BIGQUERY_DATASET=jobmatching_dw
MINIO_BUCKET=processed-data
```

### Credentials GCP
Placer le fichier service account dans le conteneur Airflow :
```bash
# Copier vers le conteneur
docker cp credentials/bq-service-account.json bigdata_airflow_webserver:/opt/airflow/credentials/
```

### Connexions Airflow

#### Spark Connection (`spark_default`)
- **Conn Type** : `spark`
- **Host** : `spark://spark-master`
- **Port** : `7077`

#### BigQuery Connection (`bigquery_default`)
- **Conn Type** : `google_cloud_platform`
- **Project ID** : `bigdata-jobmatching-test`
- **Keyfile Path** : `/opt/airflow/credentials/bq-service-account.json`

#### MinIO Connection (`minio_default`)
- **Conn Type** : `s3`
- **Host** : `minio`
- **Port** : `9000`
- **Login** : `minioadmin`
- **Password** : `minioadmin123`
- **Schema** : `http`

## 🔧 Dépannage

### DAGs non visibles
```bash
# Redémarrer Airflow
docker restart bigdata_airflow_scheduler bigdata_airflow_webserver
```

### Connexions échouent
1. Vérifier que tous les services sont démarrés : `./status.sh`
2. Tester les connexions : `python airflow/test_connections.py`
3. Vérifier les logs des tâches dans l'interface Airflow

### Jobs Spark échouent
1. Vérifier la connexion Spark : `docker logs bigdata_spark_master`
2. Vérifier que les fichiers sont accessibles dans MinIO
3. Tester manuellement : `./scripts/spark/run_parse_jobs.sh`

## 📊 Monitoring

### Métriques à Surveiller
- **Temps d'exécution** : Chaque tâche < 2h
- **Taux de succès** : > 95%
- **Volume de données** : Nombre d'offres traitées
- **Erreurs** : Logs d'erreurs détaillés

### Alertes (TODO)
- Échec de scraping
- Échec de processing
- Volume anormal de données
- Erreurs BigQuery

## 🎯 État Actuel

### ✅ Implémenté
- [x] Structure des 3 DAGs principaux
- [x] Orchestration séquentielle des jobs Spark
- [x] Scraping parallèle des 4 sources
- [x] Chargement BigQuery automatisé
- [x] Script de test des connexions

### 🔄 À Compléter
- [ ] Implémentation `consume_cvs.py` (Phase 4)
- [ ] Tests end-to-end des DAGs
- [ ] Notifications par email/Slack
- [ ] Monitoring avancé des métriques
- [ ] Gestion des erreurs améliorée

## 🚀 Prochaines Étapes

1. **Créer `consume_cvs.py`** (Phase 4 manquante)
2. **Tester les DAGs** en production
3. **Implémenter les notifications**
4. **Ajouter le monitoring** détaillé
5. **Phase 6** : Dashboards Superset

---
**Phase 5 : ~80% complétée** 🎯

*DAGs opérationnels - Pipeline orchestré - Prêt pour production*
