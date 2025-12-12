#!/usr/bin/env python3
"""
==========================================
Spark Batch - Deduplication Jobs
==========================================
Job Spark Batch pour la déduplication des offres d'emploi inter-sources.

Source: s3a://processed-data/jobs_parsed/
Destination: s3a://processed-data/jobs_deduplicated/

Algorithme:
- Normalisation des clés (titre + entreprise + localisation)
- Calcul de similarité (Jaccard + Fuzzy)
- Clustering des doublons
- Conservation de la meilleure version
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lower, trim, regexp_replace, concat_ws,
    levenshtein, size, explode, collect_list, struct,
    row_number, when, coalesce, current_timestamp,
    date_format, arrays_zip, array_distinct, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, ArrayType
)
from pyspark.sql.window import Window
import re


def create_spark_session():
    """Crée la session Spark avec configuration MinIO"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return SparkSession.builder \
        .appName("JobOffersDeduplication") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()


def normalize_text_udf(text):
    """UDF pour normaliser le texte pour la comparaison"""
    if not text:
        return ""

    # Convertir en minuscules
    text = text.lower()

    # Supprimer la ponctuation et caractères spéciaux
    text = re.sub(r'[^\w\s]', ' ', text)

    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)

    # Supprimer les mots vides courants
    stop_words = {
        'de', 'du', 'des', 'le', 'la', 'les', 'et', 'à', 'un', 'une', 'dans',
        'pour', 'par', 'sur', 'avec', 'sans', 'sous', 'chez', 'comme', 'qui',
        'que', 'dont', 'où', 'quand', 'comment', 'pourquoi', 'si', 'alors',
        'mais', 'car', 'donc', 'or', 'ni', 'soit', 'c', 'est', 'ce', 'ci', 'ça'
    }

    words = text.split()
    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

    return ' '.join(filtered_words)


def calculate_similarity_score_udf(title1, company1, location1, title2, company2, location2):
    """
    UDF pour calculer le score de similarité entre deux offres
    Retourne un score entre 0 et 1
    """
    if not all([title1, company1, location1, title2, company2, location2]):
        return 0.0

    # Normaliser les textes
    title1_norm = normalize_text_udf(title1)
    title2_norm = normalize_text_udf(title2)
    company1_norm = normalize_text_udf(company1)
    company2_norm = normalize_text_udf(company2)
    location1_norm = normalize_text_udf(location1)
    location2_norm = normalize_text_udf(location2)

    # Score titre (poids 0.5) - Similarité Jaccard
    title_words1 = set(title1_norm.split())
    title_words2 = set(title2_norm.split())

    if not title_words1 or not title_words2:
        title_score = 0.0
    else:
        intersection = len(title_words1 & title_words2)
        union = len(title_words1 | title_words2)
        title_score = intersection / union if union > 0 else 0.0

    # Score entreprise (poids 0.3) - Exact match normalisé
    company_score = 1.0 if company1_norm == company2_norm else 0.0

    # Score localisation (poids 0.2) - Exact match normalisé
    location_score = 1.0 if location1_norm == location2_norm else 0.0

    # Score total pondéré
    total_score = (title_score * 0.5) + (company_score * 0.3) + (location_score * 0.2)

    return float(total_score)


def create_similarity_key_udf(title, company, location):
    """UDF pour créer une clé de similarité plus discriminante"""
    normalized_title = normalize_text_udf(title)
    normalized_company = normalize_text_udf(company)
    normalized_location = normalize_text_udf(location)

    # Prendre plus de mots pour être plus discriminante
    # Utiliser les 5-6 premiers mots du titre au lieu de 3
    title_words = normalized_title.split()[:6] if normalized_title else []
    company_words = normalized_company.split()[:3] if normalized_company else []
    location_words = normalized_location.split()[:2] if normalized_location else []

    # Filtrer les valeurs par défaut/génériques qui créent des collisions
    generic_company = ['entreprise', 'confidentielle', 'company', 'societe']
    generic_location = ['cote', 'ivoire', 'abidjan', 'location']
    
    # Si l'entreprise est générique, utiliser plus de mots du titre
    if company_words and all(word in generic_company for word in company_words):
        # Utiliser encore plus de mots du titre pour compenser
        title_words = normalized_title.split()[:8] if normalized_title else []
    
    # Si la localisation est générique, ignorer ou utiliser plus de mots
    if location_words and all(word in generic_location for word in location_words):
        location_words = []  # Ignorer la localisation si trop générique
    
    key_parts = title_words + company_words + location_words
    
    # Si la clé est trop courte ou vide, utiliser un hash du titre complet
    if len(key_parts) < 3:
        # Utiliser un hash des 10 premiers mots du titre normalisé
        fallback_words = normalized_title.split()[:10] if normalized_title else []
        key_parts = fallback_words if fallback_words else ['UNKNOWN']
    
    return '_'.join(key_parts) if key_parts else 'UNKNOWN'


def calculate_completeness_score(title, company, description, location, skills, salary_text):
    """Calcule un score de complétude de l'offre (0-1)"""
    score = 0.0
    total_fields = 6

    if title and len(title.strip()) > 5: score += 1
    if company and company != "Entreprise confidentielle": score += 1
    if description and len(description.strip()) > 20: score += 1
    if location and location != "Côte d'Ivoire": score += 1
    if skills and len(skills) > 0: score += 1
    if salary_text and len(salary_text.strip()) > 0: score += 1

    return score / total_fields


def select_best_offer(grouped_offers):
    """
    Sélectionne la meilleure offre parmi un groupe de doublons
    Critères prioritaires:
    1. Score de complétude
    2. Date la plus récente
    3. Source de priorité (educarriere > macarrierepro > emploi_ci > linkedin)
    """
    if not grouped_offers:
        return None

    # Trier par score de complétude décroissant, puis par date, puis par source
    source_priority = {
        'educarriere': 4,
        'macarrierepro': 3,
        'emploi_ci': 2,
        'linkedin': 1
    }

    best_offer = max(grouped_offers, key=lambda x: (
        x.get('completeness_score', 0),
        x.get('parsed_at', ''),
        source_priority.get(x.get('source', '').lower(), 0)
    ))

    return best_offer


def process_deduplication(spark, input_path, output_path):
    """
    Traite la déduplication des offres d'emploi

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source (jobs parsés)
        output_path: Chemin MinIO destination (jobs dédupliqués)
    """

    # Enregistrer les UDFs
    normalize_text = udf(normalize_text_udf, StringType())
    calculate_similarity = udf(calculate_similarity_score_udf, FloatType())
    create_similarity_key = udf(create_similarity_key_udf, StringType())
    calc_completeness = udf(calculate_completeness_score, FloatType())

    print("✅ UDFs enregistrées")

    # Lire les données parsées
    jobs_df = spark.read.parquet(input_path)
    total_jobs = jobs_df.count()

    print(f"✅ {total_jobs} offres lues depuis {input_path}")

    # Étape 1: Préparer les données avec clés de similarité
    prepared_df = jobs_df \
        .withColumn("similarity_key", create_similarity_key(col("title"), col("company"), col("location"))) \
        .withColumn("completeness_score", calc_completeness(
            col("title"), col("company"), col("description"),
            col("location"), col("skills"), col("parsed_salary_text")
        )) \
        .withColumn("normalized_title", normalize_text(col("title"))) \
        .withColumn("normalized_company", normalize_text(col("company"))) \
        .withColumn("normalized_location", normalize_text(col("location")))

    print("✅ Données préparées avec clés de similarité")
    
    # Diagnostic : compter les clés de similarité uniques
    unique_keys_count = prepared_df.select("similarity_key").distinct().count()
    print(f"📊 Diagnostic: {unique_keys_count} clés de similarité uniques sur {total_jobs} offres")
    
    # Afficher les clés les plus fréquentes
    key_distribution = prepared_df \
        .groupBy("similarity_key") \
        .count() \
        .orderBy(col("count").desc()) \
        .limit(5)
    
    print("📊 Top 5 clés de similarité les plus fréquentes:")
    key_distribution.show(truncate=False)

    # Étape 2: Grouper par clé de similarité et collecter les offres candidates
    grouped_df = prepared_df \
        .groupBy("similarity_key") \
        .agg(
            collect_list(struct(
                col("job_id"),
                col("source"),
                col("title"),
                col("company"),
                col("location"),
                col("description"),
                col("requirements"),
                col("parsed_salary_text"),
                col("contract_type"),
                col("skills"),
                col("parsed_at"),
                col("parsing_quality_score"),
                col("completeness_score"),
                col("normalized_title"),
                col("normalized_company"),
                col("normalized_location"),
                col("html_content")
            )).alias("candidate_offers")
        ) \
        .filter(size(col("candidate_offers")) > 1)  # Garder seulement les groupes avec doublons potentiels

    print(f"✅ {grouped_df.count()} groupes de doublons potentiels identifiés")

    # Étape 3: Pour chaque groupe, calculer les similarités et sélectionner la meilleure offre
    def process_duplicate_group(candidate_offers):
        """Traite un groupe de doublons potentiels"""
        if not candidate_offers or len(candidate_offers) < 2:
            return []

        # Calculer les paires de similarité
        duplicates = []

        for i in range(len(candidate_offers)):
            for j in range(i + 1, len(candidate_offers)):
                offer1 = candidate_offers[i]
                offer2 = candidate_offers[j]

                similarity = calculate_similarity_score_udf(
                    offer1.title, offer1.company, offer1.location,
                    offer2.title, offer2.company, offer2.location
                )

                if similarity >= 0.85:  # Seuil de similarité élevé (augmenté de 0.7 à 0.85)
                    duplicates.append({
                        'offer1_id': offer1.job_id,
                        'offer2_id': offer2.job_id,
                        'similarity_score': similarity,
                        'group_size': len(candidate_offers)
                    })

        return duplicates

    # UDF pour traiter les groupes de doublons
    process_duplicates_udf = udf(process_duplicate_group, ArrayType(StructType([
        StructField("offer1_id", StringType()),
        StructField("offer2_id", StringType()),
        StructField("similarity_score", FloatType()),
        StructField("group_size", IntegerType())
    ])))

    # Appliquer la détection de doublons
    duplicates_df = grouped_df \
        .withColumn("duplicate_pairs", process_duplicates_udf(col("candidate_offers"))) \
        .withColumn("duplicate_pair", explode(col("duplicate_pairs"))) \
        .select(
            col("duplicate_pair.offer1_id").alias("job_id_1"),
            col("duplicate_pair.offer2_id").alias("job_id_2"),
            col("duplicate_pair.similarity_score"),
            col("duplicate_pair.group_size")
        ) \
        .filter(col("similarity_score") >= 0.85)  # Seuil augmenté pour être plus strict

    print(f"✅ {duplicates_df.count()} paires de doublons détectées")

    # Étape 4: Pour chaque groupe de doublons (basé sur similarity_key), 
    # garder l'offre avec le meilleur completeness_score
    # Créer une fenêtre pour identifier la meilleure offre de chaque groupe
    window_spec = Window.partitionBy("similarity_key").orderBy(
        col("completeness_score").desc(), 
        col("parsing_quality_score").desc()
    )
    
    # Identifier les offres dans des groupes avec doublons
    prepared_with_rank = prepared_df \
        .join(
            grouped_df.select("similarity_key").withColumn("has_duplicates", lit(True)),
            "similarity_key",
            "left"
        ) \
        .withColumn("rank", 
            when(col("has_duplicates").isNotNull(), 
                 row_number().over(window_spec)
            ).otherwise(lit(1))
        )

    # Garder :
    # 1. Les offres qui ne sont pas dans des groupes de doublons (has_duplicates is NULL)
    # 2. L'offre avec rank=1 de chaque groupe de doublons (meilleure offre)
    best_offers_df = prepared_with_rank \
        .filter(
            (col("has_duplicates").isNull()) |  # Offres sans doublons
            (col("rank") == 1)  # Meilleure offre de chaque groupe
        ) \
        .drop("has_duplicates", "rank", "similarity_key", "normalized_title", "normalized_company", "normalized_location")

    print(f"✅ {best_offers_df.count()} offres uniques conservées après déduplication")

    # Étape 5: Finaliser les données dédupliquées
    deduplicated_df = best_offers_df \
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
            col("completeness_score"),
            current_timestamp().alias("deduplicated_at")
        )

    # Écrire les données dédupliquées
    deduplicated_df.write \
        .mode("overwrite") \
        .partitionBy("source") \
        .parquet(output_path)

    print(f"✅ Données dédupliquées écrites vers {output_path}")

    # Statistiques finales
    final_count = deduplicated_df.count()
    duplicates_removed = total_jobs - final_count

    print("📊 Statistiques de déduplication:")
    print(f"   Offres initiales: {total_jobs}")
    print(f"   Offres finales: {final_count}")
    print(f"   Doublons supprimés: {duplicates_removed}")
    print(".1f")

    return {
        "initial_count": total_jobs,
        "final_count": final_count,
        "duplicates_removed": duplicates_removed,
        "status": "SUCCESS"
    }


def main():
    """Fonction principale"""
    print("🚀 Démarrage de la déduplication Spark Batch - Offres d'emploi")

    # Configuration
    input_bucket = os.getenv("MINIO_BUCKET", "processed-data")
    output_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    input_path = f"s3a://{input_bucket}/jobs_parsed"
    output_path = f"s3a://{output_bucket}/jobs_deduplicated"

    print(f"📋 Configuration:")
    print(f"   Input: {input_path}")
    print(f"   Output: {output_path}")

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Traiter la déduplication
        result = process_deduplication(spark, input_path, output_path)

        if result["status"] == "SUCCESS":
            print("✅ Déduplication terminée avec succès")
            print("📊 Statistiques:")
            for key, value in result.items():
                if key != "status":
                    print(f"   {key}: {value}")
        else:
            print("❌ Échec de la déduplication")
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
