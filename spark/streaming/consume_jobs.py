#!/usr/bin/env python3
"""
==========================================
Spark Streaming - Consommation Jobs Kafka
==========================================
Job Spark Streaming pour consommer les offres d'emploi depuis Kafka
et les écrire dans le Data Lake MinIO en format Parquet.

Topic Kafka: job-offers-raw
Destination: s3a://processed-data/jobs/
Partitionnement: scraped_date, source
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, schema_of_json, to_date, regexp_replace,
    when, lit, current_timestamp, year, month, dayofmonth
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, TimestampType, ArrayType
)


def create_spark_session():
    """Crée la session Spark avec configuration Kafka et MinIO"""
    return SparkSession.builder \
        .appName("JobOffersConsumer") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.streaming.backpressure.enabled", "true") \
        .config("spark.streaming.kafka.maxRatePerPartition", "1000") \
        .getOrCreate()


def get_job_schema():
    """Définit le schéma des données d'offres d'emploi"""
    return StructType([
        # Métadonnées scraping
        StructField("job_id", StringType(), True),
        StructField("scraped_at", StringType(), True),  # String ISO format
        StructField("scraper_version", StringType(), True),
        StructField("country", StringType(), True),

        # Informations de base de l'offre
        StructField("title", StringType(), True),
        StructField("company", StringType(), True),
        StructField("location", StringType(), True),
        StructField("description", StringType(), True),
        StructField("requirements", StringType(), True),

        # Informations salariales
        StructField("salary", StructType([
            StructField("amount", IntegerType(), True),
            StructField("currency", StringType(), True),
            StructField("period", StringType(), True),
            StructField("original_text", StringType(), True)
        ]), True),

        # Métadonnées enrichies
        StructField("contract_type", StringType(), True),
        StructField("experience_level", StringType(), True),
        StructField("industry", StringType(), True),
        StructField("skills", ArrayType(StringType()), True),

        # Source
        StructField("source", StringType(), True),
        StructField("source_url", StringType(), True),

        # Données brutes (optionnel)
        StructField("html_content", StringType(), True)
    ])


def process_job_offers(spark, kafka_bootstrap_servers, topic_name, minio_bucket):
    """
    Traite le stream d'offres d'emploi depuis Kafka

    Args:
        spark: SparkSession
        kafka_bootstrap_servers: Serveurs Kafka
        topic_name: Nom du topic
        minio_bucket: Bucket MinIO destination
    """

    # Schéma des données
    job_schema = get_job_schema()

    # Lire depuis Kafka
    kafka_df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
        .option("subscribe", topic_name) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    print("✅ Connexion Kafka établie")

    # Parser le JSON depuis la valeur Kafka
    parsed_df = kafka_df \
        .selectExpr("CAST(key AS STRING) as kafka_key", "CAST(value AS STRING) as json_value") \
        .select(
            col("kafka_key"),
            from_json(col("json_value"), job_schema).alias("job_data")
        ) \
        .select("kafka_key", "job_data.*")

    print("✅ Parsing JSON configuré")

    # Transformations basiques
    transformed_df = parsed_df \
        .withColumn("scraped_date", to_date(col("scraped_at"))) \
        .withColumn("scraped_year", year(col("scraped_date"))) \
        .withColumn("scraped_month", month(col("scraped_date"))) \
        .withColumn("scraped_day", dayofmonth(col("scraped_date"))) \
        .withColumn("processed_at", current_timestamp()) \
        .withColumn("salary_amount", col("salary.amount")) \
        .withColumn("salary_currency", col("salary.currency")) \
        .withColumn("salary_period", col("salary.period"))

    # Nettoyer les données
    cleaned_df = transformed_df \
        .withColumn("title", regexp_replace(col("title"), r"\s+", " ")) \
        .withColumn("company", regexp_replace(col("company"), r"\s+", " ")) \
        .withColumn("location", regexp_replace(col("location"), r"\s+", " ")) \
        .withColumn("contract_type",
                   when(col("contract_type").isNull(), "Non spécifié")
                   .otherwise(col("contract_type"))) \
        .withColumn("experience_level",
                   when(col("experience_level").isNull(), "Non spécifié")
                   .otherwise(col("experience_level"))) \
        .withColumn("industry",
                   when(col("industry").isNull(), "Autre")
                   .otherwise(col("industry")))

    print("✅ Transformations appliquées")

    # Configuration de l'écriture
    checkpoint_location = f"s3a://{minio_bucket}/checkpoints/jobs_consumer/"
    output_path = f"s3a://{minio_bucket}/processed-data/jobs/"

    # Écrire en streaming avec partitionnement
    query = cleaned_df \
        .writeStream \
        .format("parquet") \
        .option("path", output_path) \
        .option("checkpointLocation", checkpoint_location) \
        .partitionBy("scraped_date", "source") \
        .outputMode("append") \
        .trigger(processingTime="30 seconds") \
        .start()

    print(f"✅ Streaming démarré vers {output_path}")
    print(f"📍 Checkpoint: {checkpoint_location}")
    print("🎯 Partitionnement: scraped_date, source")
    return query


def main():
    """Fonction principale"""
    print("🚀 Démarrage du consommateur Spark Streaming - Offres d'emploi")

    # Configuration depuis variables d'environnement
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    topic = "job-offers-raw"
    minio_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    print(f"📋 Configuration:")
    print(f"   Kafka: {kafka_servers}")
    print(f"   Topic: {topic}")
    print(f"   MinIO Bucket: {minio_bucket}")

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Démarrer le traitement
        query = process_job_offers(spark, kafka_servers, topic, minio_bucket)

        # Attendre la terminaison
        print("⏳ Streaming en cours... (Ctrl+C pour arrêter)")
        query.awaitTermination()

    except KeyboardInterrupt:
        print("\n🛑 Interruption utilisateur")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
    finally:
        if 'spark' in locals():
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
