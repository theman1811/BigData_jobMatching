# 📊 Diagramme de Séquences UML - Pipeline Big Data Job Matching

## 🎯 Vue d'ensemble

Ce document explique le diagramme de séquences UML (`sequence_diagram.xml`) qui décrit le pipeline complet de traitement des données Big Data pour le projet Job Matching.

### Objectif
Le diagramme illustre la **séquence temporelle des interactions** entre les différents composants du système Big Data, depuis le déclenchement du scraping jusqu'à la visualisation des données.

---

## 🏗️ Composants représentés (Lifelines)

Chaque ligne verticale représente un **composant actif** du système :

| Composant | Rôle | Couleur |
|-----------|------|---------|
| **Data Analyst** | Utilisateur déclenchant les processus | 🟡 Jaune |
| **Airflow DAG** | Orchestrateur des pipelines | 🟣 Violet |
| **Scraper Service** | Service de web scraping | 🔴 Rouge |
| **Kafka Broker** | Bus de messages (streaming) | 🔵 Bleu clair |
| **Spark Streaming Job** | Traitement temps réel des données | 🟢 Vert menthe |
| **MinIO Client** | Stockage objet (Data Lake) | 🟢 Turquoise |
| **BigQuery Loader** | Chargement vers Data Warehouse | 🟠 Orange |
| **Superset Dashboard** | Interface de visualisation BI | ⚪ Gris |

---

## 🔄 Séquence des interactions

### Phase 1 : Déclenchement (Y=200)
```
Data Analyst → Airflow DAG : triggerScrapingDAG()
    ↓
Airflow DAG → Scraper Service : startScraping()
```

**Explication** : L'analyste de données déclenche manuellement un DAG Airflow qui lance le processus de scraping.

### Phase 2 : Ingestion (Y=280-380)
```
Scraper Service → Kafka Broker : <<async>> publish(job-offers-raw, cvs-raw)
Scraper Service → MinIO Client : saveRawFiles(html, pdf)
```

**Explication** : Le scraper collecte les données des sites web et les publie simultanément dans Kafka (pour traitement temps réel) et MinIO (pour archivage brut).

### Phase 3 : Traitement (Y=420-600)
```
Kafka Broker → Spark Streaming Job : <<async stream>> consume(job-offers-raw, cvs-raw)
Spark Streaming Job → Spark Streaming Job : processNLP(text, skills)
Spark Streaming Job → MinIO Client : saveProcessedData(parquet)
Spark Streaming Job → Kafka Broker : <<async>> publish(job-offers-parsed, cvs-parsed)
```

**Explication** : Spark consomme en continu les messages Kafka, applique le traitement NLP (extraction de compétences, normalisation), sauvegarde les données structurées dans MinIO, puis republie les données enrichies dans Kafka.

### Phase 4 : Chargement (Y=720-750)
```
Airflow DAG → BigQuery Loader : loadBatchData()
BigQuery Loader → MinIO Client : readProcessedData()
```

**Explication** : Selon un planning (DAG quotidien), Airflow déclenche le chargement batch des données traitées depuis MinIO vers BigQuery.

### Phase 5 : Visualisation (Y=850-890)
```
Data Analyst → Superset Dashboard : createDashboard()
Superset Dashboard → BigQuery Loader : <<async query>> SELECT * FROM fact_jobs, dim_skills
```

**Explication** : L'analyste crée des tableaux de bord dans Superset qui interrogent directement BigQuery pour afficher les analyses temps réel.

---

## 📨 Types de messages

### 🔵 Messages synchrones (appels de méthodes)
- **Flèche pleine** avec retour en pointillé
- Attendent une réponse avant de continuer
- Exemples : `triggerScrapingDAG()`, `startScraping()`, `saveRawFiles()`

### 🟠 Messages asynchrones (événements)
- **Flèche ouverte pointillée** sans retour obligatoire
- Ne bloquent pas l'exécution
- Types :
  - `<<async>>` : Publication/consommation simple
  - `<<async stream>>` : Traitement en continu
  - `<<async query>>` : Requêtes de données

---

## 📏 Conventions UML utilisées

### Lignes de vie (Lifelines)
- **Trait vertical pointillé** : Représente l'existence temporelle du composant
- **Boîte d'activation** : Rectangle fin montrant la période d'activité

### Stéréotypes
- `<<async>>` : Message asynchrone
- `<<async stream>>` : Streaming continu
- `<<async query>>` : Requête de données

### Couleurs
- **Bleu (#1ba1e2)** : Messages synchrones (appels)
- **Orange (#ff9900)** : Messages asynchrones (événements)
- **Gris (#666666)** : Messages de retour

---

## 🔧 Comment utiliser le diagramme

### Ouverture dans draw.io
1. Aller sur [app.diagrams.net](https://app.diagrams.net)
2. **Fichier → Ouvrir** → Sélectionner `sequence_diagram.xml`
3. Le diagramme s'affiche avec toutes les interactions

### Lecture du diagramme
1. **Commencer par le haut** : Les interactions se déroulent de haut en bas
2. **Suivre les flèches** : Chaque flèche représente un message entre composants
3. **Regarder les couleurs** : Bleu = synchrone, Orange = asynchrone
4. **Observer les boîtes** : Les rectangles fins montrent quand chaque composant est actif

### Points d'attention
- **Kafka** : Sert de bus de messages asynchrone entre scraper et Spark
- **MinIO** : Stockage persistant (Data Lake) pour toutes les données
- **BigQuery** : Data Warehouse pour les requêtes analytiques
- **Airflow** : Orchestrateur qui déclenche les processus batch

---

## 🔄 Flux de données résumé

```
Sites Web → Scraper → Kafka → Spark → MinIO → Airflow → BigQuery → Superset
(Indeed,    (Service)   (Bus)   (NLP)   (Lake)    (Batch)    (DW)      (BI)
 LinkedIn,
 etc.)
```

### Données collectées
- **Offres d'emploi** : Titre, entreprise, salaire, compétences, localisation
- **CVs candidats** : Compétences, expérience, prétentions salariales

### Transformations appliquées
- **Parsing HTML/PDF** → Extraction structurée
- **NLP** → Normalisation compétences, entités nommées
- **Dédoublonnage** → Élimination des doublons
- **Enrichissement** → Calcul scores de matching

---

## 📚 Références

- [Standard UML Sequence Diagrams](https://www.uml.org/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Spark Documentation](https://spark.apache.org/docs/)
- [Google BigQuery](https://cloud.google.com/bigquery)
- [Apache Superset](https://superset.apache.org/)

---

*Dernière mise à jour : Novembre 2024*
