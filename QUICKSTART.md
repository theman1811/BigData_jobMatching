# ⚡ Guide de Démarrage Rapide

Ce guide vous permet de démarrer la plateforme BigData en quelques minutes.

## 📋 Prérequis

- Docker Desktop installé et lancé
- 8 GB RAM minimum disponible
- 10 GB espace disque

## 🚀 Démarrage en 3 étapes

### Étape 1 : Vérifier les prérequis

```bash
# Rendre le script exécutable
chmod +x scripts/setup/check_prerequisites.sh

# Exécuter la vérification
./scripts/setup/check_prerequisites.sh
```

### Étape 2 : Démarrer la plateforme

```bash
# Rendre le script exécutable
chmod +x start.sh

# Démarrer tous les services
./start.sh
```

⏳ **Attendre environ 2-3 minutes** que tous les services démarrent.

### Étape 3 : Vérifier que tout fonctionne

```bash
# Rendre le script exécutable
chmod +x status.sh

# Vérifier le statut
./status.sh
```

## 🌐 Accéder aux Interfaces Web

Une fois démarrée, la plateforme expose plusieurs interfaces :

| Service | URL | Credentials |
|---------|-----|-------------|
| **Kafka UI** | http://localhost:8080 | Aucun |
| **Spark Master** | http://localhost:8082 | Aucun |
| **Spark Worker 1** | http://localhost:8083 | Aucun |
| **Spark Worker 2** | http://localhost:8084 | Aucun |
| **Airflow** | http://localhost:8085 | user: `airflow`<br>pass: `airflow` |
| **Jupyter** | http://localhost:8888 | token: `bigdata2024` |

## 📊 Vérifier que les Services Fonctionnent

### Kafka

```bash
# Ouvrir http://localhost:8080
# Vous devriez voir l'interface Kafka UI
```

### Spark

```bash
# Ouvrir http://localhost:8082
# Vous devriez voir le Spark Master avec 2 workers connectés
```

### Airflow

```bash
# Ouvrir http://localhost:8085
# Login: airflow / airflow
# Vous devriez voir le dashboard Airflow
```

### Jupyter

```bash
# Ouvrir http://localhost:8888
# Token: bigdata2024
# Vous devriez voir l'interface JupyterLab
```

## 🧪 Créer vos Premiers Topics Kafka

```bash
# Rendre le script exécutable
chmod +x scripts/setup/create_kafka_topics.sh

# Créer les topics de test
./scripts/setup/create_kafka_topics.sh
```

## 📝 Tester PySpark dans Jupyter

1. Ouvrir Jupyter : http://localhost:8888 (token: `bigdata2024`)
2. Créer un nouveau notebook Python
3. Coller ce code de test :

```python
from pyspark.sql import SparkSession

# Créer une session Spark
spark = SparkSession.builder \
    .appName("Test BigData") \
    .master("spark://spark-master:7077") \
    .getOrCreate()

# Créer un DataFrame de test
data = [("Alice", 25), ("Bob", 30), ("Charlie", 35)]
df = spark.createDataFrame(data, ["name", "age"])

# Afficher
df.show()

# Arrêter
spark.stop()

print("✅ PySpark fonctionne !")
```

4. Exécuter (Shift + Enter)
5. Vérifier le résultat

## 🛑 Arrêter la Plateforme

```bash
# Rendre le script exécutable (si pas déjà fait)
chmod +x stop.sh

# Arrêter tous les services
./stop.sh
```

## 🧹 Nettoyer Complètement (optionnel)

⚠️ **Attention** : Ceci supprime toutes les données !

```bash
# Rendre le script exécutable (si pas déjà fait)
chmod +x clean.sh

# Nettoyer
./clean.sh
```

## ❓ Problèmes Courants

### Les conteneurs ne démarrent pas

**Solution** :
```bash
# Vérifier que Docker est lancé
docker info

# Voir les logs
docker-compose logs -f

# Redémarrer
./stop.sh
./start.sh
```

### "Port already in use"

**Solution** :
```bash
# Trouver le processus qui utilise le port (exemple port 8080)
lsof -i :8080

# Arrêter le processus ou changer le port dans docker-compose.yml
```

### Manque de mémoire

**Solution** :
1. Ouvrir Docker Desktop
2. Preferences → Resources
3. Augmenter la RAM à 8 GB minimum
4. Apply & Restart

### Airflow ne démarre pas

**Solution** :
```bash
# Les logs Airflow peuvent prendre 1-2 minutes
# Attendre et vérifier les logs
docker-compose logs -f airflow-webserver

# Si problème de permissions
chmod -R 777 ./airflow/logs ./airflow/dags
./stop.sh
./start.sh
```

## 📚 Prochaines Étapes

### Phase 1 : Environnement Local ✅

Vous avez maintenant une plateforme Big Data complète qui tourne localement !

### Phase 2 : Configuration GCP

Pour configurer Google Cloud Platform (GCS et BigQuery) :

```bash
# Lire le guide GCP
cat docs/setup_gcp.md

# Ou ouvrir dans votre éditeur
```

### Phase 3 : Créer vos Pipelines

1. **Créer un producteur Kafka** dans `kafka/producers/`
2. **Créer un job Spark** dans `spark/batch/` ou `spark/streaming/`
3. **Créer un DAG Airflow** dans `airflow/dags/`
4. **Charger dans BigQuery** via Spark
5. **Créer un dashboard** dans Looker Studio

## 📖 Documentation Complète

- **README.md** : Vue d'ensemble du projet
- **docs/architecture.md** : Architecture détaillée
- **docs/setup_gcp.md** : Configuration Google Cloud
- **requirements.txt** : Dépendances Python

## 🆘 Besoin d'Aide ?

1. Vérifier les logs :
   ```bash
   docker-compose logs -f [nom-du-service]
   ```

2. Vérifier le statut :
   ```bash
   ./status.sh
   ```

3. Consulter la documentation officielle :
   - [Kafka](https://kafka.apache.org/documentation/)
   - [Spark](https://spark.apache.org/docs/latest/)
   - [Airflow](https://airflow.apache.org/docs/)

---

**Bon développement ! 🚀**

