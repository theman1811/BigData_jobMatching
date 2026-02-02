#!/usr/bin/env python3
"""
==========================================
Spark Batch - Extract Skills NLP
==========================================
Job Spark Batch pour l'extraction de compétences via NLP depuis les offres d'emploi.

Source: s3a://processed-data/jobs_parsed/
Destination: s3a://processed-data/jobs_enriched_skills/

Algorithme:
- Extraction NLP avec spaCy
- Détection compétences techniques
- Classification par catégorie
- Enrichissement données
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lower, trim, regexp_replace, concat_ws,
    explode, collect_list, struct, when, coalesce,
    current_timestamp, date_format, size, array_distinct,
    arrays_zip, array_union, lit, array
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, ArrayType
)
from pyspark.sql.window import Window

# Imports NLP - spaCy sera chargé dans les UDFs
import re

# Import pour le logging
from logging_utils import write_processing_log


def create_spark_session():
    """Crée la session Spark avec configuration MinIO"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return SparkSession.builder \
        .appName("SkillsExtractorNLP") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.jars.packages",
                "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2") \
        .getOrCreate()


def load_spacy_udf():
    """Charge spaCy pour l'extraction NLP"""
    try:
        import spacy
        # Utiliser un modèle léger pour la performance
        nlp = spacy.load("en_core_web_sm")
        return nlp
    except Exception as e:
        print(f"Erreur chargement spaCy: {e}")
        return None


def extract_skills_nlp_udf(text):
    """
    UDF pour extraire les compétences via NLP avec spaCy
    Retourne une liste de compétences détectées
    """
    if not text or len(text.strip()) < 10:
        return []

    try:
        # Charger spaCy (sera mis en cache par Spark)
        nlp = load_spacy_udf()
        if not nlp:
            return []

        # Catalogue étendu de compétences par catégorie
        skills_catalog = {
            # Programmation
            "python": ["python", "py", "pandas", "numpy", "django", "flask", "fastapi"],
            "java": ["java", "spring", "hibernate", "maven", "gradle"],
            "javascript": ["javascript", "js", "node.js", "react", "vue", "angular", "typescript"],
            "csharp": ["c#", ".net", "asp.net", "entity framework"],
            "php": ["php", "laravel", "symfony", "wordpress"],
            "ruby": ["ruby", "rails", "ror"],
            "go": ["go", "golang"],
            "rust": ["rust"],
            "scala": ["scala", "akka"],
            "kotlin": ["kotlin", "android"],
            "swift": ["swift", "ios"],
            "r": ["r", "rstudio", "shiny"],
            "matlab": ["matlab"],
            "sas": ["sas"],

            # Bases de données
            "sql": ["sql", "mysql", "postgresql", "oracle", "sqlite", "tsql"],
            "nosql": ["mongodb", "cassandra", "redis", "elasticsearch", "dynamodb"],
            "bigdata": ["hadoop", "spark", "kafka", "hive", "pig", "flume", "sqoop"],

            # Cloud & DevOps
            "aws": ["aws", "ec2", "s3", "lambda", "rds", "cloudformation"],
            "azure": ["azure", "blob storage", "azure functions"],
            "gcp": ["gcp", "google cloud", "bigquery", "cloud storage"],
            "docker": ["docker", "container", "kubernetes", "k8s"],
            "terraform": ["terraform", "infrastructure as code"],
            "jenkins": ["jenkins", "ci/cd", "gitlab ci", "github actions"],
            "linux": ["linux", "bash", "shell", "ubuntu", "centos"],

            # BI & Analytics
            "tableau": ["tableau", "tableau desktop", "tableau server"],
            "powerbi": ["power bi", "powerbi", "dax"],
            "qlik": ["qlik", "qlikview", "qliksense"],
            "excel": ["excel", "vba", "macros"],
            "sap": ["sap", "sap hana", "abap"],

            # Méthodologies
            "agile": ["agile", "scrum", "kanban", "sprint"],
            "devops": ["devops", "ci/cd", "continuous integration"],
            "tdd": ["tdd", "test driven development"],
            "bdd": ["bdd", "behavior driven development"],

            # Frameworks Web
            "frontend": ["html", "css", "bootstrap", "tailwind", "sass"],
            "backend": ["api", "rest", "graphql", "microservices", "soap"],

            # Data Science
            "machine_learning": ["machine learning", "ml", "tensorflow", "pytorch", "scikit-learn"],
            "deep_learning": ["deep learning", "neural networks", "cnn", "rnn"],
            "data_science": ["data science", "statistics", "probability", "data analysis"]
        }

        # Prétraitement du texte
        text_lower = text.lower()

        # Nettoyer le texte
        text_clean = re.sub(r'[^\w\s]', ' ', text_lower)
        text_clean = re.sub(r'\s+', ' ', text_clean)

        detected_skills = []

        # Recherche exacte dans le catalogue
        for category, skill_variants in skills_catalog.items():
            for variant in skill_variants:
                if variant in text_clean:
                    # Utiliser le nom canonique de la catégorie
                    skill_name = category.replace('_', ' ').title()
                    if skill_name not in detected_skills:
                        detected_skills.append(skill_name)

        # Extraction par patterns regex pour les compétences moins communes
        additional_patterns = [
            r'\b(c\+\+|cpp)\b',
            r'\b(react\.js|reactjs)\b',
            r'\b(node\.js|nodejs)\b',
            r'\b(express\.js|expressjs)\b',
            r'\b(jquery)\b',
            r'\b(bootstrap)\b',
            r'\b(tailwind)\b',
            r'\b(sass|scss)\b',
            r'\b(webpack)\b',
            r'\b(gulp|grunt)\b'
        ]

        for pattern in additional_patterns:
            if re.search(pattern, text_clean):
                skill_match = re.search(pattern, text_clean).group(1)
                skill_name = skill_match.replace('.', '').title()
                if skill_name not in detected_skills:
                    detected_skills.append(skill_name)

        # NLP avec spaCy pour extraction contextuelle
        if nlp:
            try:
                doc = nlp(text[:1000])  # Limiter la taille pour performance

                # Extraction de termes techniques (NOUN + PROPN)
                technical_terms = []
                for token in doc:
                    if token.pos_ in ['NOUN', 'PROPN'] and len(token.text) > 2:
                        # Chercher des termes composés
                        if token.dep_ in ['compound', 'amod']:
                            compound = f"{token.head.text} {token.text}"
                            technical_terms.append(compound.lower())

                # Filtrer et ajouter les termes techniques pertinents
                for term in technical_terms[:5]:  # Limiter à 5 termes
                    if term not in ['experience', 'years', 'skills', 'knowledge', 'ability']:
                        term_title = term.title()
                        if term_title not in detected_skills:
                            detected_skills.append(term_title)

            except Exception as e:
                print(f"Erreur NLP spaCy: {e}")

        return list(set(detected_skills))  # Éliminer les doublons

    except Exception as e:
        print(f"Erreur extraction compétences: {e}")
        return []


def classify_skill_category_udf(skill_name):
    """Classifie une compétence dans une catégorie"""
    if not skill_name:
        return "Autre"

    skill_lower = skill_name.lower()

    categories = {
        "Programmation": [
            "python", "java", "javascript", "csharp", "php", "ruby", "go", "rust",
            "scala", "kotlin", "swift", "r", "matlab", "sas", "c++", "cpp"
        ],
        "Base de Données": [
            "sql", "nosql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch"
        ],
        "Big Data": [
            "hadoop", "spark", "kafka", "hive", "bigquery", "data science"
        ],
        "Cloud": [
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform"
        ],
        "DevOps": [
            "jenkins", "linux", "bash", "ci/cd", "devops"
        ],
        "BI & Analytics": [
            "tableau", "powerbi", "qlik", "excel", "sap"
        ],
        "Web": [
            "html", "css", "react", "vue", "angular", "bootstrap", "tailwind"
        ],
        "IA & ML": [
            "machine learning", "deep learning", "tensorflow", "pytorch"
        ],
        "Méthodologies": [
            "agile", "scrum", "kanban", "tdd", "bdd"
        ]
    }

    for category, skills in categories.items():
        if any(s in skill_lower for s in skills):
            return category

    return "Technique"


def calculate_skill_confidence_udf(skill_name, context_text):
    """Calcule un score de confiance pour une compétence extraite"""
    if not skill_name or not context_text:
        return 0.5

    skill_lower = skill_name.lower()
    context_lower = context_text.lower()

    # Score basé sur la fréquence et le contexte
    frequency = context_lower.count(skill_lower)

    # Bonus si la compétence apparaît plusieurs fois
    confidence = min(0.9, 0.6 + (frequency * 0.1))

    # Bonus si c'est dans une liste de compétences
    if any(word in context_lower for word in ['compétences', 'skills', 'technologies', 'outils']):
        confidence += 0.1

    return float(confidence)


def process_skills_extraction(spark, input_path, output_path):
    """
    Traite l'extraction de compétences NLP

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source
        output_path: Chemin MinIO destination
    """

    # Enregistrer les UDFs Python
    extract_skills_nlp = udf(extract_skills_nlp_udf, ArrayType(StringType()))
    classify_category = udf(classify_skill_category_udf, StringType())
    calculate_confidence = udf(calculate_skill_confidence_udf, FloatType())

    print("✅ UDFs enregistrées")

    # Lire les données parsées
    jobs_df = spark.read.parquet(input_path)
    total_jobs = jobs_df.count()

    print(f"✅ {total_jobs} offres lues depuis {input_path}")

    # Étape 1: Extraction NLP des compétences
    enriched_df = jobs_df \
        .withColumn("nlp_extracted_skills",
                   extract_skills_nlp(
                       coalesce(col("description"), lit("")) + " " +
                       coalesce(col("requirements"), lit(""))
                   ))

    print("✅ Extraction NLP des compétences effectuée")

    # Étape 2: Fusion avec compétences existantes
    final_skills_df = enriched_df \
        .withColumn("all_skills",
                   array_union(
                       coalesce(col("skills"), array()),
                       coalesce(col("nlp_extracted_skills"), array())
                   )) \
        .withColumn("unique_skills", array_distinct(col("all_skills")))

    print("✅ Fusion des compétences existantes et extraites")

    # Étape 3: Enrichissement avec métadonnées des compétences
    # Utiliser le pattern explode → apply UDFs → collect_list
    # car les UDFs Python ne peuvent pas être utilisées directement dans transform()
    
    # Créer une colonne temporaire pour le contexte (description + requirements)
    skills_with_context_df = final_skills_df \
        .withColumn("skill_context",
                   concat_ws(" ",
                       coalesce(col("description"), lit("")),
                       coalesce(col("requirements"), lit(""))
                   ))
    
    # Vérifier s'il y a des compétences à traiter
    jobs_with_skills_count = skills_with_context_df.filter(size(col("unique_skills")) > 0).count()
    print(f"📊 Offres avec compétences à enrichir: {jobs_with_skills_count}")
    
    if jobs_with_skills_count > 0:
        # Exploser les compétences pour appliquer les UDFs individuellement
        exploded_df = skills_with_context_df \
            .filter(size(col("unique_skills")) > 0) \
            .select(
                col("job_id"),
                col("skill_context"),
                explode(col("unique_skills")).alias("skill_name")
            )
        
        # Appliquer les UDFs à chaque compétence
        skills_enriched_df = exploded_df \
            .withColumn("skill_category", classify_category(col("skill_name"))) \
            .withColumn("skill_confidence", calculate_confidence(col("skill_name"), col("skill_context")))
        
        # Regrouper les compétences enrichies par job_id
        skills_grouped_df = skills_enriched_df \
            .groupBy("job_id") \
            .agg(
                collect_list(
                    struct(
                        col("skill_name").alias("0"),
                        col("skill_category").alias("1"),
                        col("skill_confidence").alias("2")
                    )
                ).alias("skills_with_metadata")
            )
        
        # Joindre avec le DataFrame original
        skills_with_metadata_df = skills_with_context_df \
            .join(skills_grouped_df, "job_id", "left") \
            .withColumn("skills_with_metadata",
                       coalesce(col("skills_with_metadata"), array())) \
            .drop("skill_context")
    else:
        # Aucune compétence à enrichir
        skills_with_metadata_df = skills_with_context_df \
            .withColumn("skills_with_metadata", array()) \
            .drop("skill_context")

    print("✅ Métadonnées des compétences ajoutées")

    # Étape 4: Préparation données finales
    output_df = skills_with_metadata_df \
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
            col("unique_skills").alias("skills"),
            col("skills_with_metadata"),
            col("parsed_at"),
            col("parsing_quality_score"),
            current_timestamp().alias("skills_extracted_at")
        )

    # Écrire les données enrichies
    output_df.write \
        .mode("overwrite") \
        .partitionBy("source") \
        .parquet(output_path)

    print(f"✅ Données enrichies écrites vers {output_path}")

    # Statistiques
    skills_stats_df = output_df \
        .withColumn("skills_count", size(col("skills"))) \
        .agg(
            {"skills_count": "avg"}
        ).collect()

    avg_skills = skills_stats_df[0][0] if skills_stats_df else 0

    jobs_with_skills = output_df.filter(size(col('skills')) > 0).count()
    
    print("📊 Statistiques d'extraction de compétences:")
    print(f"   Offres traitées: {total_jobs}")
    print(f"   Compétences moyennes par offre: {avg_skills:.2f}")
    print(f"   Offres avec compétences: {jobs_with_skills}")

    return {
        "total_jobs": total_jobs,
        "avg_skills_per_job": avg_skills,
        "status": "SUCCESS"
    }


def main():
    """Fonction principale"""
    print("🚀 Démarrage de l'extraction de compétences NLP - Spark Batch")

    # Configuration
    input_bucket = os.getenv("MINIO_BUCKET", "processed-data")
    output_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    input_path = f"s3a://{input_bucket}/jobs_parsed"
    output_path = f"s3a://{output_bucket}/jobs_enriched_skills"

    print(f"📋 Configuration:")
    print(f"   Input: {input_path}")
    print(f"   Output: {output_path}")

    # Variables pour le logging
    start_time = datetime.now()
    execution_id = os.getenv("AIRFLOW_RUN_ID", None)
    airflow_dag_id = os.getenv("AIRFLOW_DAG_ID", None)
    airflow_task_id = os.getenv("AIRFLOW_TASK_ID", None)
    statut = "SUCCESS"
    records_processed = 0
    error_message = None
    error_stack_trace = None

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Traiter l'extraction
        result = process_skills_extraction(spark, input_path, output_path)

        if result["status"] == "SUCCESS":
            statut = "SUCCESS"
            records_processed = result.get("total_jobs", 0)
            print("✅ Extraction de compétences terminée avec succès")
            print("📊 Statistiques:")
            for key, value in result.items():
                if key != "status":
                    print(f"   {key}: {value}")
        else:
            statut = "FAILED"
            error_message = result.get("error", "Échec de l'extraction")
            print("❌ Échec de l'extraction de compétences")
            sys.exit(1)

    except Exception as e:
        statut = "FAILED"
        error_message = str(e)
        import traceback
        error_stack_trace = traceback.format_exc()
        print(f"❌ Erreur: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Écrire le log dans BigQuery
        end_time = datetime.now()
        try:
            if 'spark' in locals():
                write_processing_log(
                    spark=spark,
                    job_name="extract_skills",
                    job_type="spark_batch",
                    start_time=start_time,
                    end_time=end_time,
                    statut=statut,
                    records_processed=records_processed,
                    records_success=records_processed if statut == "SUCCESS" else 0,
                    records_failed=0 if statut == "SUCCESS" else records_processed,
                    error_message=error_message,
                    error_stack_trace=error_stack_trace,
                    execution_id=execution_id,
                    airflow_dag_id=airflow_dag_id,
                    airflow_task_id=airflow_task_id
                )
        except Exception as log_error:
            print(f"⚠️  Erreur lors de l'écriture du log: {log_error}")
        
        if 'spark' in locals():
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
