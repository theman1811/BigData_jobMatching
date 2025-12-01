#!/usr/bin/env python3
"""
Script d'initialisation de BigQuery pour le projet job matching
"""

import os
from google.cloud import bigquery
from google.oauth2 import service_account

def init_bigquery():
    """Initialise le dataset et les tables BigQuery"""

    # Configuration depuis les variables d'environnement
    project_id = os.getenv('GCP_PROJECT_ID')
    dataset_id = os.getenv('BIGQUERY_DATASET')

    if not project_id or not dataset_id:
        raise ValueError("Variables GCP_PROJECT_ID et BIGQUERY_DATASET requises")

    # Configuration des credentials
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if cred_path and os.path.exists(cred_path):
        credentials = service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        client = bigquery.Client(project=project_id, credentials=credentials)
    else:
        # Fallback vers les credentials par défaut
        client = bigquery.Client(project=project_id)
    
    # Création du dataset
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "EU"
    dataset.description = "Data Warehouse pour le système de matching d'emplois"
    
    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✅ Dataset {dataset_id} créé/vérifié")
    except Exception as e:
        print(f"❌ Erreur création dataset: {e}")
        return False
    
    # Lecture et exécution du script de création des tables
    schema_file = "/tmp/create_tables.sql"
    
    if not os.path.exists(schema_file):
        print(f"❌ Fichier {schema_file} introuvable")
        return False
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # Exécution des commandes SQL (séparées par ';')
    statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
    
    for statement in statements:
        if statement:
            try:
                query_job = client.query(statement)
                query_job.result()  # Attendre la fin
                print(f"✅ Exécuté: {statement[:50]}...")
            except Exception as e:
                print(f"❌ Erreur SQL: {e}")
                print(f"Statement: {statement[:100]}...")
    
    print("✅ Initialisation BigQuery terminée")
    return True

if __name__ == "__main__":
    init_bigquery()