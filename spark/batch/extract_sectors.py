#!/usr/bin/env python3
"""
==========================================
Spark Batch - Extract Sectors
==========================================
Job Spark Batch pour l'extraction et classification des secteurs d'activité.

Source: s3a://processed-data/jobs_parsed/
Destination: BigQuery (Dim_Secteur + mise à jour Fact_OffresEmploi)

Algorithme:
- Analyse titre, entreprise, description
- Classification secteurs ivoiriens
- Hiérarchie avec categorie_parent
- Enrichissement BigQuery
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lower, trim, regexp_replace, concat_ws,
    when, coalesce, current_timestamp, date_format,
    lit, struct, explode, collect_list, array_distinct,
    row_number, desc, count, avg
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, ArrayType
)
from pyspark.sql.window import Window

import re


def create_spark_session():
    """Crée la session Spark avec configuration BigQuery et GCS"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    # Le chemin des credentials dépend du contexte (Airflow driver vs Spark executor)
    gcp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/opt/spark/credentials/bq-service-account.json")
    
    return SparkSession.builder \
        .appName("SectorExtractor") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem") \
        .config("spark.hadoop.fs.AbstractFileSystem.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFS") \
        .config("spark.hadoop.google.cloud.auth.service.account.json.keyfile", "/opt/spark/credentials/bq-service-account.json") \
        .config("spark.hadoop.google.cloud.auth.service.account.enable", "true") \
        .config("spark.jars.packages",
                "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2,"
                "com.google.cloud.bigdataoss:gcs-connector:hadoop3-2.2.5") \
        .getOrCreate()


def classify_sector_udf(title, company, description, location):
    """
    UDF pour classifier une offre dans un secteur d'activité ivoirien

    Retourne un struct avec:
    - secteur_id: ID unique du secteur
    - secteur_nom: Nom du secteur
    - categorie_parent: Catégorie parente
    - confidence: Score de confiance (0-1)
    """
    if not any([title, company, description]):
        return {
            "secteur_id": "SECT_INCONNU",
            "secteur_nom": "Secteur inconnu",
            "categorie_parent": "INCONNU",
            "confidence": 0.0
        }

    # Combiner tout le texte pour l'analyse
    full_text = " ".join(filter(None, [title, company, description, location]))
    full_text_lower = full_text.lower()

    # Catalogue des secteurs économiques ivoiriens
    secteurs_ivoiriens = {
        # TECHNOLOGIES & NUMÉRIQUE
        "SECT_TECH": {
            "nom": "Technologies & Informatique",
            "parent": "SERVICES_NUMERIQUES",
            "mots_cles": [
                "informatique", "développeur", "développement", "programmeur", "it", "digital",
                "web", "mobile", "application", "logiciel", "data", "analyste", "scientist",
                "intelligence artificielle", "ia", "machine learning", "big data", "cloud",
                "aws", "azure", "google cloud", "devops", "docker", "kubernetes", "cyber",
                "sécurité informatique", "réseau", "système", "base de données", "sql",
                "python", "java", "javascript", "php", "react", "angular", "vue", ".net",
                "c#", "c++", "swift", "kotlin", "scala", "r", "spark", "hadoop", "kafka"
            ],
            "entreprises": [
                "orange", "mtn", "moov", "canal+", "nsia", "ecobank", "sgbci", "baci",
                "uba", "boa", "vsat", "africa systems", "business intelligence"
            ]
        },

        # TÉLÉCOMMUNICATIONS
        "SECT_TELECOM": {
            "nom": "Télécommunications",
            "parent": "SERVICES_NUMERIQUES",
            "mots_cles": [
                "télécom", "téléphone", "mobile", "réseau", "4g", "5g", "fibre", "internet",
                "opérateur", "gsm", "vsat", "satellite", "communication", "data center",
                "cloud computing", "iot", "objets connectés", "smart city"
            ],
            "entreprises": [
                "orange", "mtn", "moov", "canal+", "africa systems", "côte d'ivoire telecom",
                "ivoire telecom", "telecel", "green", "yoomee", "nsia", "ecobank"
            ]
        },

        # BANQUE & FINANCE
        "SECT_FINANCE": {
            "nom": "Banque & Finance",
            "parent": "SERVICES_FINANCIERS",
            "mots_cles": [
                "banque", "banquier", "finance", "financier", "comptabilité", "comptable",
                "audit", "auditeur", "contrôleur", "gestion", "budget", "trésorerie",
                "crédit", "prêt", "épargne", "assurance", "assureur", "actuaire",
                "risk management", "compliance", "reglementation", "banque centrale",
                "microfinance", "sfd", "institution financière", "bfc", "bci", "bicici"
            ],
            "entreprises": [
                "nsia", "ecobank", "sgbci", "baci", "boa", "bicici", "bfc", "uba",
                "banque Atlantique", "banque de l'habitat", "biic", "bnii", "bsic",
                "banque centrale", "bceao", "microcred", "fefi", "finadev"
            ]
        },

        # ASSURANCE
        "SECT_ASSURANCE": {
            "nom": "Assurance",
            "parent": "SERVICES_FINANCIERS",
            "mots_cles": [
                "assurance", "assureur", "courtier", "risque", "sinistre", "indemnisation",
                "actuaire", "souscription", "réassurance", "mutuelle", "prévoyance",
                "santé", "automobile", "habitation", "responsabilité civile"
            ],
            "entreprises": [
                "nsia assurance", "allianz", "axa", "generali", "atlantic assurance",
                "saar", "sun assurance", "agra", "sicore", "scac", "mutuelle"
            ]
        },

        # AGRO-INDUSTRIE
        "SECT_AGRO": {
            "nom": "Agro-industrie",
            "parent": "INDUSTRIE_AGRICOLE",
            "mots_cles": [
                "agriculture", "agricole", "cacao", "café", "anacarde", "hévéa", "coton",
                "palme", "huile", "sucre", "riz", "maïs", "banane", "ananas", "mangue",
                "transformation", "agro-alimentaire", "coopérative", "plantation",
                "irrigation", "semence", "engrais", "pesticide", "export", "filiale"
            ],
            "entreprises": [
                "sifca", "sapc", "cabc", "coris", "bnetd", "palmci", "sucaf",
                "ivoria", "olam", "cargill", "louis dreyfus", "socapalm", "bollore",
                "africa food", "chococam", "sicor", "coopérative", "plantation"
            ]
        },

        # BTP & CONSTRUCTION
        "SECT_BTP": {
            "nom": "BTP & Construction",
            "parent": "INDUSTRIE_CONSTRUCTION",
            "mots_cles": [
                "construction", "bâtiment", "travaux publics", "tp", "btp", "architecte",
                "ingénieur", "chantier", "maçon", "électricien", "plombier", "peintre",
                "ciment", "béton", "acier", "infrastructure", "route", "pont", "tunnel",
                "immeuble", "résidentiel", "commercial", "projet", "urbanisme"
            ],
            "entreprises": [
                "bollore", "bouygues", "vinci", "eiffage", "razel", "somagec", "setraci",
                "poti", "scetia", "sogea", "dumez", "citra", "sogea-satamur", "icf",
                "cimaf", "ciments de la côte", "unibéton", "béton cellulaire"
            ]
        },

        # COMMERCE & DISTRIBUTION
        "SECT_COMMERCE": {
            "nom": "Commerce & Distribution",
            "parent": "SERVICES_COMMERCIAUX",
            "mots_cles": [
                "commerce", "vente", "commercial", "distribution", "import", "export",
                "grossiste", "détaillant", "magasin", "boutique", "supermarché", "hypermarché",
                "franchise", "représentant", "agent commercial", "business development",
                "marketing", "promotion", "client", "relation client", "crm"
            ],
            "entreprises": [
                "bollore", "cfa", "carrefour", "supermarché", "pharmacie", "jumia",
                "kilimall", "yango market", "capri cavanni", "tcb", "société générale",
                "shell", "total", "ivoire énergie", "distribution", "import-export"
            ]
        },

        # SANTÉ & PHARMACIE
        "SECT_SANTE": {
            "nom": "Santé & Pharmacie",
            "parent": "SERVICES_SANTE",
            "mots_cles": [
                "médecin", "docteur", "infirmier", "pharmacien", "chirurgien", "hospitalier",
                "clinique", "hôpital", "cabinet", "laboratoire", "analyse", "radiologie",
                "pharmacie", "médicament", "soins", "santé publique", "épidémiologie",
                "vaccination", "maladie", "traitement", "diagnostic", "urgence"
            ],
            "entreprises": [
                "pharmacie", "clinique", "hôpital", "polyclinique", "laboratoire",
                "bioanalyse", "radiologie", "pharmacie populaire", "sanofi", "pfizer",
                "gsk", "novartis", "msd", "roche", "bms", "jnj", "abbott"
            ]
        },

        # ÉDUCATION & FORMATION
        "SECT_EDUCATION": {
            "nom": "Éducation & Formation",
            "parent": "SERVICES_EDUCATION",
            "mots_cles": [
                "enseignant", "professeur", "éducation", "école", "université", "formation",
                "pédagogie", "didactique", "apprentissage", "stage", "alternance",
                "enseignement supérieur", "secondaire", "primaire", "maternelle",
                "langue", "mathématiques", "sciences", "lettres", "histoire", "géographie"
            ],
            "entreprises": [
                "université", "inphb", "esp", "ens", "institut", "école", "lycée",
                "collège", "maternelle", "centre de formation", "orange digital center",
                "microsoft innovation center", "google", "ibm", "cfa", "afdb"
            ]
        },

        # ADMINISTRATION PUBLIQUE
        "SECT_ADMIN": {
            "nom": "Administration Publique",
            "parent": "SERVICES_PUBLICS",
            "mots_cles": [
                "administration", "fonction publique", "ministère", "secrétariat", "d'état",
                "préfet", "sous-préfet", "mairie", "commune", "collectivité", "territoriale",
                "service public", "état", "gouvernement", "ambassade", "consulat",
                "police", "gendarmerie", "armée", "défense", "justice", "tribunal"
            ],
            "entreprises": [
                "état", "gouvernement", "présidence", "primature", "ministère", "dgi",
                "dgf", "douane", "police", "gendarmerie", "armée", "justice", "tribunal",
                "cour", "ambassade", "consulat", "onu", "pnud", "fao", "afdb"
            ]
        },

        # HÔTELLERIE & TOURISME
        "SECT_HOTELLERIE": {
            "nom": "Hôtellerie & Tourisme",
            "parent": "SERVICES_TOURISTIQUES",
            "mots_cles": [
                "hôtel", "hôtelier", "restaurant", "tourisme", "touriste", "guide",
                "agence de voyage", "réceptif", "loisir", "événement", "congrès",
                "séminaire", "mariage", "cérémonie", "traiteur", "cuisine", "chef"
            ],
            "entreprises": [
                "novotel", "ibis", "radisson", "azalai", "tropico", "sofitel", "hilton",
                "marriott", "accor", "restaurant", "agence de voyage", "discovery",
                "visit côte d'ivoire", "office du tourisme", "congress center"
            ]
        },

        # TRANSPORT & LOGISTIQUE
        "SECT_TRANSPORT": {
            "nom": "Transport & Logistique",
            "parent": "SERVICES_TRANSPORT",
            "mots_cles": [
                "transport", "logistique", "livreur", "chauffeur", "camion", "véhicule",
                "aéroport", "avion", "pilote", "steward", "cargo", "port", "dock",
                "transit", "supply chain", "entreposage", "warehouse", "distribution"
            ],
            "entreprises": [
                "bollore", "sdv", "maersk", "cma cgm", "air côte d'ivoire", "air france",
                "ethiopian", "turkish airlines", "brussels airlines", "port autonome",
                "sag", "setrag", "utc", "société de transport", "dhl", "ups", "fedex"
            ]
        },

        # ÉNERGIE & MINES
        "SECT_ENERGIE": {
            "nom": "Énergie & Mines",
            "parent": "INDUSTRIE_ENERGIE",
            "mots_cles": [
                "énergie", "electricité", "cie", "hydrocarbure", "pétrole", "gaz",
                "mine", "exploitation", "géologue", "forage", "sismique", "pipeline",
                "raffinerie", "distribution", "éolien", "solaire", "renouvelable"
            ],
            "entreprises": [
                "cie", "petroci", "total", "shell", "esso", "ivoire énergie", "aip",
                "geoci", "sodemi", "société minière", "endiama", "china minmetals"
            ]
        },

        # INDUSTRIE MANUFACTURIÈRE
        "SECT_MANUFACTURE": {
            "nom": "Industrie Manufacturière",
            "parent": "INDUSTRIE_MANUFACTURE",
            "mots_cles": [
                "industrie", "manufacture", "usine", "production", "qualité", "process",
                "maintenance", "ingénieur", "technicien", "opérateur", "ligne production",
                "emballage", "conditionnement", "supply chain", "lean", "six sigma"
            ],
            "entreprises": [
                "bollore", "sifca", "unilever", "nestle", "p&g", "coca cola", "pepsi",
                "sabc", "palmci", "cimaf", "béton cellulaire", "plastic industry"
            ]
        }
    }

    # Recherche du secteur le plus probable
    best_match = {
        "secteur_id": "SECT_INCONNU",
        "secteur_nom": "Secteur inconnu",
        "categorie_parent": "INCONNU",
        "confidence": 0.0
    }

    for secteur_id, secteur_info in secteurs_ivoiriens.items():
        confidence = 0.0
        matches = 0

        # Recherche dans les mots-clés
        for mot_cle in secteur_info["mots_cles"]:
            if mot_cle in full_text_lower:
                matches += 1

        if matches > 0:
            confidence += min(matches * 0.3, 0.8)  # Max 0.8 pour mots-clés

        # Recherche dans les entreprises
        for entreprise in secteur_info["entreprises"]:
            if entreprise.lower() in full_text_lower:
                confidence += 0.5  # Bonus fort pour entreprise connue
                break

        # Bonus pour mots dans le titre (plus important)
        title_lower = (title or "").lower()
        for mot_cle in secteur_info["mots_cles"]:
            if mot_cle in title_lower:
                confidence += 0.2

        # Si meilleure confiance trouvée
        if confidence > best_match["confidence"]:
            best_match = {
                "secteur_id": secteur_id,
                "secteur_nom": secteur_info["nom"],
                "categorie_parent": secteur_info["parent"],
                "confidence": min(confidence, 1.0)
            }

    return best_match




def process_sector_extraction(spark, input_path, bigquery_dataset, gcp_project_id):
    """
    Traite l'extraction et classification des secteurs

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source
        bigquery_dataset: Dataset BigQuery
        gcp_project_id: Projet GCP
    """

    # Enregistrer les UDFs
    classify_sector = udf(classify_sector_udf,
                         StructType([
                             StructField("secteur_id", StringType()),
                             StructField("secteur_nom", StringType()),
                             StructField("categorie_parent", StringType()),
                             StructField("confidence", FloatType())
                         ]))

    print("✅ UDFs enregistrées")

    # Lire les données parsées
    jobs_df = spark.read.parquet(input_path)
    total_jobs = jobs_df.count()

    print(f"✅ {total_jobs} offres lues depuis {input_path}")

    # Étape 1: Classification des secteurs
    classified_df = jobs_df \
        .withColumn("sector_classification",
                   classify_sector(col("title"), col("company"), col("description"), col("location"))) \
        .withColumn("secteur_id", col("sector_classification.secteur_id")) \
        .withColumn("secteur_nom", col("sector_classification.secteur_nom")) \
        .withColumn("categorie_parent", col("sector_classification.categorie_parent")) \
        .withColumn("sector_confidence", col("sector_classification.confidence"))

    print("✅ Classification sectorielle effectuée")

    # Étape 2: Statistiques des classifications
    sector_stats = classified_df \
        .groupBy("secteur_id", "secteur_nom", "categorie_parent") \
        .agg(
            count("*").alias("offres_count"),
            (avg("sector_confidence") * 100).alias("avg_confidence_pct")
        ) \
        .orderBy(desc("offres_count"))

    print("📊 Répartition par secteur:")
    sector_stats.show(20, False)

    # Étape 3: Préparer les données pour Dim_Secteur
    dim_secteur_df = classified_df \
        .select("secteur_id", "secteur_nom", "categorie_parent") \
        .distinct() \
        .withColumn("description",
                   when(col("secteur_id") == "SECT_INCONNU", "Secteur non classifié")
                   .otherwise(concat_ws(" - ", col("secteur_nom"), col("categorie_parent")))) \
        .withColumn("created_at", current_timestamp()) \
        .filter(col("secteur_id").isNotNull()) \
        .dropDuplicates(["secteur_id"])

    print(f"✅ {dim_secteur_df.count()} secteurs uniques identifiés")

    # Étape 4: Charger Dim_Secteur dans BigQuery (optionnel, non bloquant)
    bq_options = {
        "project": gcp_project_id,
        "dataset": bigquery_dataset,
        "temporaryGcsBucket": f"{gcp_project_id}-temp-spark-bq"
    }

    bq_success = False
    try:
        secteur_table = f"{bigquery_dataset}.Dim_Secteur"

        dim_secteur_df.write \
            .format("bigquery") \
            .option("table", secteur_table) \
            .options(**bq_options) \
            .mode("append") \
            .save()

        print(f"✅ Dim_Secteur chargée dans BigQuery ({dim_secteur_df.count()} secteurs)")
        bq_success = True

    except Exception as e:
        print(f"⚠️  Erreur chargement Dim_Secteur dans BigQuery (non bloquant): {e}")
        print("   → Continuation avec sauvegarde MinIO uniquement")
        bq_success = False

    # Étape 5: Préparer les données finales avec vrais secteur_id
    enriched_jobs_df = classified_df \
        .withColumn("source", coalesce(col("source"), lit("unknown"))) \
        .select(
            col("job_id"),
            col("source"),
            col("title"),
            col("company"),
            col("description"),
            col("requirements"),
            col("location"),
            col("parsed_salary_text"),
            col("contract_type"),
            col("skills"),
            col("parsed_at"),
            col("parsing_quality_score"),
            col("secteur_id"),
            col("secteur_nom"),
            col("categorie_parent"),
            col("sector_confidence"),
            current_timestamp().alias("sector_processed_at")
        )

    # Sauvegarder les données enrichies dans MinIO
    output_path = f"s3a://processed-data/jobs_enriched_sectors"
    enriched_jobs_df.write \
        .mode("overwrite") \
        .partitionBy("source") \
        .parquet(output_path)

    print(f"✅ Données enrichies sauvegardées vers {output_path}")

    # Statistiques finales
    final_stats = enriched_jobs_df \
        .select(
            count(when(col("secteur_id") != "SECT_INCONNU", 1)).alias("classified_jobs"),
            (avg("sector_confidence") * 100).alias("avg_confidence_pct"),
            count(when(col("sector_confidence") > 0.7, 1)).alias("high_confidence_jobs")
        ).collect()[0]

    classified_count = final_stats["classified_jobs"]
    avg_confidence = final_stats["avg_confidence_pct"]
    high_confidence_count = final_stats["high_confidence_jobs"]

    print("📊 Statistiques finales:")
    print(f"   Offres classifiées: {classified_count}/{total_jobs}")
    print(".1f")
    print(f"   Haute confiance (>70%): {high_confidence_count}")

    return {
        "total_jobs": total_jobs,
        "classified_jobs": classified_count,
        "classification_rate": (classified_count / total_jobs) * 100 if total_jobs > 0 else 0,
        "avg_confidence": avg_confidence,
        "high_confidence_jobs": high_confidence_count,
        "dim_secteur_count": dim_secteur_df.count(),
        "bigquery_success": bq_success,
        "status": "SUCCESS"
    }


def main():
    """Fonction principale"""
    print("🚀 Démarrage de l'extraction des secteurs - Spark Batch")

    # Configuration
    input_bucket = os.getenv("MINIO_BUCKET", "processed-data")
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "noble-anvil-479619-h9")
    bigquery_dataset = os.getenv("BIGQUERY_DATASET", "jobmatching_dw")

    input_path = f"s3a://{input_bucket}/jobs_parsed"

    print(f"📋 Configuration:")
    print(f"   Input: {input_path}")
    print(f"   GCP Project: {gcp_project_id}")
    print(f"   BigQuery Dataset: {bigquery_dataset}")

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Traiter l'extraction des secteurs
        result = process_sector_extraction(spark, input_path, bigquery_dataset, gcp_project_id)

        if result["status"] == "SUCCESS":
            print("✅ Extraction des secteurs terminée avec succès")
            print("📊 Statistiques:")
            for key, value in result.items():
                if key != "status":
                    print(f"   {key}: {value}")
        else:
            print(f"❌ Échec de l'extraction: {result.get('error', 'Erreur inconnue')}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'spark' in locals():
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
