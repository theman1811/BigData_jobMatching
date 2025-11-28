# 📝 Changelog - Architecture Modernisée

## [2.0.0] - 2024-11-24

### 🎯 Migration Complète de l'Architecture

#### ➕ Ajouté

**Nouveaux Services**
- ✅ **MinIO** : Data Lake S3-compatible local (remplace GCS)
- ✅ **Apache Superset** : Plateforme BI open-source (remplace Looker Studio)
- ✅ **Redis** : Cache pour Airflow et Superset
- ✅ **Scrapers Container** : Service dédié au web scraping
- ✅ **Superset Init** : Container d'initialisation Superset
- ✅ **MinIO Init** : Container d'initialisation des buckets

**Fonctionnalités**
- ✅ Couche de scraping web intégrée (Scrapy, Selenium, Playwright)
- ✅ Traitement NLP pour extraction d'informations
- ✅ Parsing de CVs (PDF, DOCX)
- ✅ Support S3A dans Spark pour accès MinIO
- ✅ Dashboard BI avec Superset
- ✅ Multi-database PostgreSQL (Airflow + Superset)

**Fichiers de Configuration**
- ✅ `.env.example` : Template variables d'environnement
- ✅ `config/spark-defaults.conf` : Configuration Spark + S3
- ✅ `config/superset_config.py` : Configuration Superset
- ✅ `docker/postgres/init-multiple-databases.sh` : Init multi-DB
- ✅ `docker/scrapers/Dockerfile` : Container scrapers
- ✅ `docker/scrapers/scraper_daemon.py` : Daemon de scraping
- ✅ `docker/scrapers/requirements.txt` : Dépendances scrapers

**Documentation**
- ✅ `ARCHITECTURE_UPDATE.md` : Détails des changements
- ✅ `QUICKSTART_NEW.md` : Guide de démarrage rapide mis à jour
- ✅ `SETUP_COMPLETE.md` : Guide de configuration complète
- ✅ `README.md` : Documentation mise à jour

**Dépendances Python**
- ✅ Web Scraping : scrapy, beautifulsoup4, selenium, playwright
- ✅ NLP : spacy, nltk, langdetect
- ✅ CV Parsing : pdfplumber, PyPDF2, python-docx
- ✅ MinIO : boto3, minio, s3fs
- ✅ BI : apache-superset

#### 🔄 Modifié

**Kafka**
- 🔄 Migration vers **KRaft mode** (sans Zookeeper)
- 🔄 Configuration simplifiée
- 🔄 Cluster ID : `MkU3OEVBNTcwNTJENDM2Qk`
- 🔄 Listeners : PLAINTEXT + CONTROLLER
- 🔄 Format des logs au premier démarrage

**Spark**
- 🔄 Configuration S3A pour accès MinIO
- 🔄 Endpoints : `http://minio:9000`
- 🔄 Volumes : ajout de `/config/spark-defaults.conf`
- 🔄 Variables d'environnement AWS (pour MinIO)

**Airflow**
- 🔄 Ajout variables MinIO/S3
- 🔄 Volumes : ajout `/kafka` pour accès aux scrapers
- 🔄 Dépendance sur Redis

**PostgreSQL**
- 🔄 Support de 2 bases de données : `airflow` et `superset`
- 🔄 Script d'initialisation multi-database
- 🔄 Variable : `POSTGRES_MULTIPLE_DATABASES`

**Jupyter**
- 🔄 Installation packages scraping et NLP
- 🔄 Configuration MinIO/S3
- 🔄 Volumes : ajout `/kafka`

**Scripts Shell**
- 🔄 `start.sh` : Ajout MinIO, Superset, création dossiers
- 🔄 `status.sh` : Ajout nouveaux services
- 🔄 Création dossiers : `data/scraped`, `kafka/schemas`, `config`, `docker/`

**Requirements**
- 🔄 `requirements.txt` : Ajout 30+ nouvelles dépendances

#### ❌ Supprimé

**Services**
- ❌ **Zookeeper** : Remplacé par Kafka KRaft
  - Plus besoin de coordination externe
  - Architecture simplifiée
  - -1 conteneur Docker
  - ~500 MB RAM économisée

**Cloud Dependencies**
- ❌ GCS pour Data Lake : Remplacé par MinIO local
- ❌ Looker Studio : Remplacé par Superset

**Volumes**
- ❌ `zookeeper_data`
- ❌ `zookeeper_logs`

### 📊 Comparaison Avant/Après

#### Services Docker

| Version | Conteneurs | Description |
|---------|------------|-------------|
| **v1.0** | 11 actifs | Zookeeper, Kafka, Spark (3), Airflow (3), PostgreSQL, Jupyter |
| **v2.0** | 15 actifs | Kafka KRaft, MinIO, Spark (3), Airflow (3), Superset, PostgreSQL, Redis, Scrapers, Jupyter |

#### Ports

**Nouveaux ports** :
- `9000` : MinIO API
- `9001` : MinIO Console
- `6379` : Redis
- `8088` : Superset

**Ports modifiés** : Aucun

**Ports supprimés** :
- `2181` : Zookeeper (plus nécessaire)

#### Ressources

| Métrique | v1.0 | v2.0 | Δ |
|----------|------|------|---|
| RAM minimum | 8 GB | 10 GB | +2 GB |
| RAM recommandée | 12 GB | 12 GB | 0 |
| Conteneurs actifs | 11 | 15 | +4 |
| Conteneurs one-shot | 1 | 2 | +1 |
| Espace disque | 10 GB | 20 GB | +10 GB |

### 🎯 Impact sur le Projet

#### Avantages

1. **Développement 100% local** 
   - Pas besoin de GCS pour développer
   - MinIO illimité (limité par disque)
   - Tests plus rapides

2. **Architecture moderne**
   - Kafka KRaft (futur de Kafka)
   - Pas de Zookeeper (déprécié)
   - Plus simple à maintenir

3. **BI puissante**
   - Superset > Looker Studio
   - Plus de fonctionnalités
   - Customisable
   - SQL Lab intégré

4. **Coûts**
   - 0€ pour développement
   - BigQuery Free Tier suffisant
   - Pas de surprises de facturation

5. **Compétences**
   - Web scraping à grande échelle
   - Architecture Big Data moderne
   - Technologies open-source

#### Défis

1. **Complexité initiale**
   - +4 conteneurs à gérer
   - Plus de configuration
   - Courbe d'apprentissage

2. **Ressources**
   - +2 GB RAM nécessaire
   - +10 GB disque
   - CPU plus sollicité

3. **Maintenance**
   - Plus de services à monitorer
   - Plus de logs à suivre
   - Plus de tests nécessaires

### 🔄 Migration depuis v1.0

Si vous avez une installation v1.0 existante :

```bash
# 1. Sauvegarder les données existantes
docker-compose exec postgres pg_dump airflow > backup.sql

# 2. Arrêter tous les services
./stop.sh

# 3. Sauvegarder les volumes (optionnel)
docker volume ls

# 4. Nettoyer l'ancienne installation
./clean.sh

# 5. Mettre à jour les fichiers
git pull  # ou copier les nouveaux fichiers

# 6. Démarrer la nouvelle version
./start.sh

# 7. Restaurer les données (si nécessaire)
docker-compose exec postgres psql -U airflow -d airflow < backup.sql
```

### 📈 Roadmap Future

#### v2.1 (Décembre 2024)
- [ ] Scrapers fonctionnels (Indeed, LinkedIn, WTTJ, Apec)
- [ ] Jobs Spark de parsing HTML/PDF
- [ ] DAGs Airflow de scraping quotidien
- [ ] Dashboards Superset de base

#### v2.2 (Janvier 2025)
- [ ] Extraction NLP avancée (compétences, salaires)
- [ ] Matching offres-CVs
- [ ] Déduplication intelligente
- [ ] Alertes et notifications

#### v2.3 (Février 2025)
- [ ] Machine Learning (prédiction salaires)
- [ ] Recommandations personnalisées
- [ ] API REST pour accès aux données
- [ ] Tests automatisés complets

#### v3.0 (Mars 2025)
- [ ] Mode production (Kubernetes)
- [ ] Monitoring avancé (Prometheus + Grafana)
- [ ] CI/CD complet
- [ ] Documentation interactive

### 🐛 Bugs Connus

Aucun bug connu pour le moment.

### 🔐 Sécurité

**Changements de sécurité** :
- ⚠️ Credentials par défaut (à changer en production)
- ✅ Réseau Docker isolé
- ✅ Pas d'exposition publique par défaut

**À faire avant production** :
- [ ] Changer tous les passwords
- [ ] Activer SSL/TLS
- [ ] Configurer firewall
- [ ] Activer authentification Kafka
- [ ] Sécuriser MinIO (TLS)

### 📚 Références

**Technologies ajoutées** :
- [Kafka KRaft](https://kafka.apache.org/documentation/#kraft) - v3.3+
- [MinIO](https://min.io/) - Latest
- [Apache Superset](https://superset.apache.org/) - 3.0+
- [Scrapy](https://scrapy.org/) - 2.11+
- [spaCy](https://spacy.io/) - 3.7+

### 👥 Contributeurs

- Architecture : Équipe Big Data
- Date : 24 novembre 2024
- Version : 2.0.0

---

**Pour plus de détails, voir :**
- `ARCHITECTURE_UPDATE.md` - Changements architecturaux
- `SETUP_COMPLETE.md` - Guide de configuration
- `QUICKSTART_NEW.md` - Guide de démarrage rapide

