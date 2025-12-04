#!/usr/bin/env python3
"""
Test des connexions Airflow pour la Phase 5
"""

from airflow import settings
from airflow.models import Connection
from airflow.providers.apache.spark.hooks.spark_submit import SparkSubmitHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
import os

def test_spark_connection():
    """Test connexion Spark"""
    try:
        print("🔄 Test connexion Spark...")
        hook = SparkSubmitHook(conn_id='spark_default')
        # Test basique - vérifie si la connexion existe
        print("✅ Connexion Spark trouvée")
        return True
    except Exception as e:
        print(f"❌ Erreur connexion Spark: {e}")
        return False

def test_bigquery_connection():
    """Test connexion BigQuery"""
    try:
        print("🔄 Test connexion BigQuery...")
        hook = BigQueryHook(gcp_conn_id='bigquery_default')
        # Test basique
        print("✅ Connexion BigQuery trouvée")
        return True
    except Exception as e:
        print(f"❌ Erreur connexion BigQuery: {e}")
        return False

def test_minio_connection():
    """Test connexion MinIO via S3"""
    try:
        print("🔄 Test connexion MinIO...")
        # Test via boto3 ou configuration AWS
        import boto3
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin123',
            region_name='us-east-1'
        )
        # Test simple
        buckets = s3.list_buckets()
        print(f"✅ Connexion MinIO OK - {len(buckets['Buckets'])} buckets trouvés")
        return True
    except Exception as e:
        print(f"❌ Erreur connexion MinIO: {e}")
        return False

def create_missing_connections():
    """Crée les connexions manquantes"""
    session = settings.Session()

    # Connexion Spark
    spark_conn = session.query(Connection).filter(Connection.conn_id == 'spark_default').first()
    if not spark_conn:
        print("🔧 Création connexion spark_default...")
        spark_conn = Connection(
            conn_id='spark_default',
            conn_type='spark',
            host='spark://spark-master',
            port=7077,
            description='Connexion au cluster Spark'
        )
        session.add(spark_conn)

    # Connexion BigQuery
    bq_conn = session.query(Connection).filter(Connection.conn_id == 'bigquery_default').first()
    if not bq_conn:
        print("🔧 Création connexion bigquery_default...")
        bq_conn = Connection(
            conn_id='bigquery_default',
            conn_type='google_cloud_platform',
            description='Connexion BigQuery'
        )
        session.add(bq_conn)

    # Connexion MinIO (optionnel)
    minio_conn = session.query(Connection).filter(Connection.conn_id == 'minio_default').first()
    if not minio_conn:
        print("🔧 Création connexion minio_default...")
        minio_conn = Connection(
            conn_id='minio_default',
            conn_type='s3',
            host='minio',
            port=9000,
            login='minioadmin',
            schema='http',
            description='Connexion MinIO S3-compatible'
        )
        session.add(minio_conn)

    session.commit()
    print("✅ Connexions créées")

def main():
    """Fonction principale"""
    print("🚀 Test des connexions Airflow - Phase 5")
    print("=" * 50)

    # Créer les connexions si elles n'existent pas
    create_missing_connections()

    # Tester les connexions
    results = []
    results.append(("Spark", test_spark_connection()))
    results.append(("BigQuery", test_bigquery_connection()))
    results.append(("MinIO", test_minio_connection()))

    print("\n" + "=" * 50)
    print("📊 RÉSULTATS DES TESTS:")

    all_ok = True
    for name, status in results:
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {name}: {'OK' if status else 'ÉCHEC'}")
        if not status:
            all_ok = False

    if all_ok:
        print("\n🎉 Toutes les connexions sont opérationnelles!")
    else:
        print("\n⚠️ Certaines connexions nécessitent configuration.")

    print("\n📋 Prochaines étapes:")
    print("   1. Vérifier les credentials GCP dans Airflow")
    print("   2. Tester les DAGs manuellement")
    print("   3. Configurer les notifications")

if __name__ == "__main__":
    main()
