#!/usr/bin/env python3
"""
Fusionne les petits fichiers HTML bruts en blocs plus gros pour réduire
le nombre de fichiers/splits lors du parsing.

Source: s3a://<SOURCE_BUCKET>/*.html (par défaut scraped-jobs)
Cible : s3a://<SOURCE_BUCKET>/<TARGET_PREFIX>/part-*.html (par défaut prefix "merged")

Paramètres d'environnement :
- SOURCE_BUCKET (def: scraped-jobs)
- TARGET_PREFIX (def: merged)
- MERGE_PARTITIONS (def: 50)  -> nombre de fichiers de sortie
- SPARK_MASTER (def: spark://spark-master:7077)
"""

import os
import sys
from pyspark.sql import SparkSession


def create_spark_session():
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return SparkSession.builder \
        .appName("MergeSmallHtmlFiles") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.files.maxPartitionBytes", os.getenv("MAX_PARTITION_BYTES", "134217728")) \
        .getOrCreate()


def main():
    source_bucket = os.getenv("SOURCE_BUCKET", "scraped-jobs")
    target_prefix = os.getenv("TARGET_PREFIX", "merged").strip("/")
    merge_partitions = int(os.getenv("MERGE_PARTITIONS", "50"))

    source_path = f"s3a://{source_bucket}/*.html"
    target_path = f"s3a://{source_bucket}/{target_prefix}"

    print("🚀 Fusion des fichiers HTML")
    print(f"   Source : {source_path}")
    print(f"   Cible  : {target_path}")
    print(f"   Fichiers de sortie : ~{merge_partitions}")

    spark = None
    try:
        spark = create_spark_session()
        sc = spark.sparkContext

        # Supprimer le répertoire cible s'il existe (évite FileAlreadyExistsException)
        hadoop_conf = sc._jsc.hadoopConfiguration()
        fs = sc._jvm.org.apache.hadoop.fs.FileSystem.get(
            sc._jvm.java.net.URI(target_path), hadoop_conf
        )
        target_uri = sc._jvm.java.net.URI(target_path)
        target_path_obj = sc._jvm.org.apache.hadoop.fs.Path(target_uri.getPath())
        
        if fs.exists(target_path_obj):
            print(f"⚠️  Répertoire {target_path} existe déjà, suppression...")
            fs.delete(target_path_obj, True)  # True = récursif
            print(f"✅ Répertoire {target_path} supprimé")

        # wholeTextFiles lit chaque fichier entier ; minPartitions permet de regrouper
        rdd = sc.wholeTextFiles(source_path, minPartitions=merge_partitions).map(lambda kv: kv[1])

        # Coalesce pour forcer le nombre de fichiers de sortie
        rdd.coalesce(merge_partitions).saveAsTextFile(target_path)

        print("✅ Fusion terminée")
    except Exception as e:
        print(f"❌ Erreur fusion: {e}")
        sys.exit(1)
    finally:
        if spark:
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
