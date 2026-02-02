#!/usr/bin/env python3
"""
==========================================
Spark Batch - Extract Salary
==========================================
Job Spark Batch pour l'extraction et normalisation des salaires depuis les offres d'emploi.

Source: s3a://processed-data/jobs_parsed/
Destination: s3a://processed-data/jobs_enriched_salary/

Particularités Afrique:
- Les salaires sont souvent non précisés
- Traitement non-bloquant si salaire absent
- Normalisation FCFA
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lower, trim, regexp_replace, concat_ws,
    when, coalesce, current_timestamp, date_format,
    lit, struct, count, avg
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType
)

import re

# Import pour le logging
from logging_utils import write_processing_log


def create_spark_session():
    """Crée la session Spark avec configuration MinIO"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return SparkSession.builder \
        .appName("SalaryExtractor") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()


def parse_salary_comprehensive_udf(salary_text, description, title):
    """
    UDF complet pour parser les salaires depuis tous les champs disponibles
    Adapté au contexte africain où les salaires sont souvent absents

    Retourne un struct avec:
    - salary_min: montant minimum
    - salary_max: montant maximum
    - currency: devise détectée
    - period: période (monthly/yearly)
    - confidence: score de confiance (0-1)
    - source: source de la donnée
    """
    if not any([salary_text, description, title]):
        return {
            "salary_min": None,
            "salary_max": None,
            "currency": "FCFA",
            "period": "monthly",
            "confidence": 0.0,
            "source": "none"
        }

    # Combiner tout le texte disponible
    full_text = " ".join(filter(None, [salary_text, description, title]))
    full_text_lower = full_text.lower()

    # Patterns de salaire pour le contexte africain/ivoirien
    salary_patterns = [
        # Patterns FCFA directs
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|francs?|f\s*cf)',
        r'(?:salaire|rémunération|paye|paie)\s*:?\s*(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|francs?)',

        # Patterns en euros/dollars (conversion implicite)
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:€|eur|euros?|euros)',
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:\$|usd|dollars?)',

        # Patterns avec périodes
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|€|\$)\s*(?:par|\/)\s*(?:mois|month|mensuel)',
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|€|\$)\s*(?:par|\/)\s*(?:an|ans|year|annuel)',

        # Patterns de fourchettes
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:à|a|-)\s*(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|€|\$)',
        r'entre\s*(\d+(?:[\s\.,]\d+)*)\s*et\s*(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|€|\$)',

        # Patterns négociables
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof|€|\$)\s*(?:négociable|à négocier|selon expérience)',

        # Patterns avec expérience
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:fcfa|cfa|xof)\s*(?:selon|en fonction de)\s*(?:expérience|profil|exp)',
    ]

    best_match = None
    best_confidence = 0.0

    for pattern in salary_patterns:
        matches = re.findall(pattern, full_text_lower, re.IGNORECASE)
        if matches:
            for match in matches:
                confidence = 1.0

                # Analyser le match
                if isinstance(match, tuple):
                    # Fourchette détectée
                    try:
                        min_val = int(float(match[0].replace(' ', '').replace(',', '').replace('.', '')))
                        max_val = int(float(match[1].replace(' ', '').replace(',', '').replace('.', '')))
                        amount_min, amount_max = min_val, max_val
                        confidence = 0.9  # Fourchette = haute confiance
                    except (ValueError, IndexError):
                        continue
                else:
                    # Montant unique
                    try:
                        amount = match.replace(' ', '').replace(',', '').replace('.', '')
                        amount_min = amount_max = int(float(amount))
                        confidence = 0.8  # Montant unique = bonne confiance
                    except (ValueError, AttributeError):
                        continue

                # Détecter la devise
                if '€' in full_text_lower or 'eur' in full_text_lower or 'euros' in full_text_lower:
                    currency = "EUR"
                    # Conversion approximative EUR -> FCFA (1 EUR ≈ 655 FCFA)
                    amount_min = int(amount_min * 655)
                    amount_max = int(amount_max * 655)
                elif '$' in full_text_lower or 'usd' in full_text_lower or 'dollar' in full_text_lower:
                    currency = "USD"
                    # Conversion approximative USD -> FCFA (1 USD ≈ 600 FCFA)
                    amount_min = int(amount_min * 600)
                    amount_max = int(amount_max * 600)
                else:
                    currency = "FCFA"

                # Détecter la période
                if any(word in full_text_lower for word in ['an', 'ans', 'annuel', 'year', 'année']):
                    period = "yearly"
                    # Convertir en mensuel pour normalisation
                    amount_min = int(amount_min / 12)
                    amount_max = int(amount_max / 12)
                else:
                    period = "monthly"

                # Ajuster la confiance selon le contexte
                if 'négociable' in full_text_lower or 'à négocier' in full_text_lower:
                    confidence *= 0.8
                if 'selon expérience' in full_text_lower or 'selon profil' in full_text_lower:
                    confidence *= 0.9
                if 'minimum' in full_text_lower:
                    confidence *= 0.7

                # Garder le meilleur match
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        "salary_min": amount_min,
                        "salary_max": amount_max,
                        "currency": currency,
                        "period": period,
                        "confidence": confidence,
                        "source": "parsed"
                    }

    # Si aucun salaire trouvé, retourner une structure vide non-bloquante
    if not best_match:
        return {
            "salary_min": None,
            "salary_max": None,
            "currency": "FCFA",
            "period": "monthly",
            "confidence": 0.0,
            "source": "none"
        }

    return best_match


def infer_salary_range_udf(title, location, contract_type, extracted_salary):
    """
    UDF pour inférer une fourchette salariale basée sur le contexte
    quand aucun salaire explicite n'est trouvé
    """
    # extracted_salary est un Row PySpark, pas un dict
    if extracted_salary and extracted_salary.salary_min is not None:
        # Convertir Row en dict pour retour
        return {
            "salary_min": extracted_salary.salary_min,
            "salary_max": extracted_salary.salary_max,
            "currency": extracted_salary.currency,
            "period": extracted_salary.period,
            "confidence": extracted_salary.confidence,
            "source": extracted_salary.source
        }

    # Grille salariale approximative pour la Côte d'Ivoire (FCFA/mois)
    salary_ranges = {
        # Par niveau hiérarchique
        "junior": {"min": 150000, "max": 400000},
        "senior": {"min": 500000, "max": 1500000},
        "lead": {"min": 800000, "max": 2500000},
        "manager": {"min": 1000000, "max": 3000000},

        # Par domaine technique
        "développeur": {"min": 200000, "max": 800000},
        "data scientist": {"min": 400000, "max": 1200000},
        "devops": {"min": 350000, "max": 1000000},
        "architecte": {"min": 600000, "max": 1800000},

        # Par secteur
        "finance": {"min": 300000, "max": 1000000},
        "tech": {"min": 250000, "max": 900000},
        "marketing": {"min": 200000, "max": 600000}
    }

    title_lower = (title or "").lower()
    location_lower = (location or "").lower()

    inferred_min = None
    inferred_max = None

    # Inférence par titre
    for key, range_val in salary_ranges.items():
        if key in title_lower:
            inferred_min = range_val["min"]
            inferred_max = range_val["max"]
            break

    # Ajustement par localisation (Abidjan = +20%)
    if "abidjan" in location_lower:
        if inferred_min:
            inferred_min = int(inferred_min * 1.2)
            inferred_max = int(inferred_max * 1.2)

    # Ajustement par type de contrat (CDD = -10%)
    if contract_type and "cdd" in contract_type.lower():
        if inferred_min:
            inferred_min = int(inferred_min * 0.9)
            inferred_max = int(inferred_max * 0.9)

    if inferred_min:
        return {
            "salary_min": inferred_min,
            "salary_max": inferred_max,
            "currency": "FCFA",
            "period": "monthly",
            "confidence": 0.3,  # Faible confiance pour l'inférence
            "source": "inferred"
        }

    return {
        "salary_min": None,
        "salary_max": None,
        "currency": "FCFA",
        "period": "monthly",
        "confidence": 0.0,
        "source": "none"
    }


def normalize_salary_udf(raw_salary):
    """
    UDF pour normaliser les données salariales finales
    """
    if not raw_salary:
        return {
            "salary_min_fcfa": None,
            "salary_max_fcfa": None,
            "salary_avg_fcfa": None,
            "currency_original": "FCFA",
            "period_normalized": "monthly",
            "confidence_score": 0.0,
            "data_source": "none"
        }

    # raw_salary est un Row PySpark, accès par attribut
    salary_min = raw_salary.salary_min if raw_salary.salary_min is not None else None
    salary_max = raw_salary.salary_max if raw_salary.salary_max is not None else None

    # Calcul de la moyenne si fourchette
    if salary_min and salary_max:
        salary_avg = (salary_min + salary_max) / 2
    elif salary_min:
        salary_avg = salary_min
        salary_max = salary_min  # Même valeur pour cohérence
    elif salary_max:
        salary_avg = salary_max
        salary_min = salary_max  # Même valeur pour cohérence
    else:
        salary_avg = None

    return {
        "salary_min_fcfa": salary_min,
        "salary_max_fcfa": salary_max,
        "salary_avg_fcfa": salary_avg,
        "currency_original": raw_salary.currency if raw_salary.currency else "FCFA",
        "period_normalized": raw_salary.period if raw_salary.period else "monthly",
        "confidence_score": raw_salary.confidence if raw_salary.confidence is not None else 0.0,
        "data_source": raw_salary.source if raw_salary.source else "none"
    }


def process_salary_extraction(spark, input_path, output_path):
    """
    Traite l'extraction et normalisation des salaires

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source
        output_path: Chemin MinIO destination
    """

    # Définir le schéma pour les UDFs struct
    salary_struct_schema = StructType([
        StructField("salary_min", IntegerType(), True),
        StructField("salary_max", IntegerType(), True),
        StructField("currency", StringType(), True),
        StructField("period", StringType(), True),
        StructField("confidence", FloatType(), True),
        StructField("source", StringType(), True)
    ])

    normalized_salary_schema = StructType([
        StructField("salary_min_fcfa", IntegerType(), True),
        StructField("salary_max_fcfa", IntegerType(), True),
        StructField("salary_avg_fcfa", FloatType(), True),
        StructField("currency_original", StringType(), True),
        StructField("period_normalized", StringType(), True),
        StructField("confidence_score", FloatType(), True),
        StructField("data_source", StringType(), True)
    ])

    # Enregistrer les UDFs
    parse_salary_comprehensive = udf(parse_salary_comprehensive_udf, salary_struct_schema)
    infer_salary_range = udf(infer_salary_range_udf, salary_struct_schema)
    normalize_salary = udf(normalize_salary_udf, normalized_salary_schema)

    print("✅ UDFs enregistrées")

    # Lire les données parsées
    jobs_df = spark.read.parquet(input_path)
    total_jobs = jobs_df.count()

    print(f"✅ {total_jobs} offres lues depuis {input_path}")

    # Étape 1: Extraction complète des salaires
    salary_extracted_df = jobs_df \
        .withColumn("raw_salary_extracted",
                   parse_salary_comprehensive(
                       col("parsed_salary_text"),
                       col("description"),
                       col("title")
                   ))

    print("✅ Extraction primaire des salaires effectuée")

    # Étape 2: Inférence pour les offres sans salaire explicite (optionnel)
    # Note: Désactivé par défaut car souvent imprécis en Afrique
    salary_with_inference_df = salary_extracted_df \
        .withColumn("salary_with_inference",
                   when(col("raw_salary_extracted.confidence") == 0.0,
                       infer_salary_range(
                           col("title"),
                           col("location"),
                           col("contract_type"),
                           col("raw_salary_extracted")
                       )
                   ).otherwise(col("raw_salary_extracted"))
                   )

    print("✅ Inférence salariale appliquée (optionnelle)")

    # Étape 3: Normalisation finale
    normalized_df = salary_with_inference_df \
        .withColumn("normalized_salary", normalize_salary(col("salary_with_inference")))

    print("✅ Normalisation salariale effectuée")

    # Étape 4: Préparation données finales
    output_df = normalized_df \
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
            col("normalized_salary.salary_min_fcfa").alias("salary_min_fcfa"),
            col("normalized_salary.salary_max_fcfa").alias("salary_max_fcfa"),
            col("normalized_salary.salary_avg_fcfa").alias("salary_avg_fcfa"),
            col("normalized_salary.currency_original").alias("salary_currency_original"),
            col("normalized_salary.period_normalized").alias("salary_period"),
            col("normalized_salary.confidence_score").alias("salary_confidence"),
            col("normalized_salary.data_source").alias("salary_source"),
            current_timestamp().alias("salary_processed_at")
        )

    # Écrire les données enrichies
    output_df.write \
        .mode("overwrite") \
        .partitionBy("source") \
        .parquet(output_path)

    print(f"✅ Données enrichies écrites vers {output_path}")

    # Statistiques
    salary_stats = output_df \
        .select(
            count(when(col("salary_min_fcfa").isNotNull(), 1)).alias("jobs_with_salary"),
            avg("salary_confidence").alias("avg_confidence"),
            avg("salary_avg_fcfa").alias("avg_salary")
        ).collect()[0]

    jobs_with_salary = salary_stats["jobs_with_salary"]
    avg_confidence = salary_stats["avg_confidence"] or 0
    avg_salary = salary_stats["avg_salary"]

    print("📊 Statistiques d'extraction salariale:")
    print(f"   Offres totales: {total_jobs}")
    print(f"   Offres avec salaire: {jobs_with_salary}")
    print(".1f")
    print(".2f")
    print(".0f")

    return {
        "total_jobs": total_jobs,
        "jobs_with_salary": jobs_with_salary,
        "salary_detection_rate": (jobs_with_salary / total_jobs) * 100 if total_jobs > 0 else 0,
        "avg_confidence": avg_confidence,
        "avg_salary_fcfa": avg_salary,
        "status": "SUCCESS"
    }


def main():
    """Fonction principale"""
    print("🚀 Démarrage de l'extraction de salaires - Spark Batch")

    # Configuration
    input_bucket = os.getenv("MINIO_BUCKET", "processed-data")
    output_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    input_path = f"s3a://{input_bucket}/jobs_parsed"
    output_path = f"s3a://{output_bucket}/jobs_enriched_salary"

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
        result = process_salary_extraction(spark, input_path, output_path)

        if result["status"] == "SUCCESS":
            statut = "SUCCESS"
            records_processed = result.get("total_jobs", 0)
            print("✅ Extraction de salaires terminée avec succès")
            print("📊 Statistiques:")
            for key, value in result.items():
                if key != "status":
                    print(f"   {key}: {value}")
        else:
            statut = "FAILED"
            error_message = result.get("error", "Échec de l'extraction")
            print("❌ Échec de l'extraction de salaires")
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
                    job_name="extract_salary",
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
