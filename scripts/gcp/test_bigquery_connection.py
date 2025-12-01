#!/usr/bin/env python3
"""
Test de connexion à BigQuery
Supporte WIF et credentials JSON
"""

import os
from google.cloud import bigquery
from google.auth import default
from google.oauth2 import service_account

def get_credentials():
    """Obtenir les credentials (WIF ou JSON)"""

    project_id = os.getenv('GCP_PROJECT_ID')
    service_account_email = os.getenv('WORKLOAD_IDENTITY_SERVICE_ACCOUNT')

    if not project_id:
        print("❌ Variable GCP_PROJECT_ID manquante")
        return None

    # Essayer d'abord les credentials JSON (pour développement)
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if cred_path and os.path.exists(cred_path):
        print("🔑 Utilisation des credentials JSON...")
        try:
            credentials = service_account.Credentials.from_service_account_file(
                cred_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            return credentials
        except Exception as e:
            print(f"❌ Erreur avec credentials JSON: {e}")

    # Fallback: credentials par défaut (pour WIF ou gcloud auth)
    print("🔄 Tentative avec credentials par défaut (ADC)...")
    try:
        credentials, project = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        print("✅ Credentials ADC trouvés")
        return credentials
    except Exception as e:
        print(f"❌ Erreur ADC: {e}")
        print("💡 Solutions:")
        print("   1. Pour développement: définir GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        print("   2. Pour WIF: configurer un token OIDC valide")
        print("   3. Via gcloud: 'gcloud auth application-default login'")
        return None

def test_connection():
    """Test la connexion BigQuery et liste les tables"""
    
    project_id = os.getenv('GCP_PROJECT_ID')
    dataset_id = os.getenv('BIGQUERY_DATASET')
    
    if not project_id or not dataset_id:
        print("❌ Variables GCP_PROJECT_ID et BIGQUERY_DATASET requises")
        return False
    
    try:
        # Obtenir les credentials
        credentials = get_credentials()
        if not credentials:
            return False

        # Créer le client BigQuery avec les credentials
        client = bigquery.Client(project=project_id, credentials=credentials)
        
        # Test connexion
        datasets = list(client.list_datasets())
        dataset_names = [d.dataset_id for d in datasets]
        
        if dataset_id in dataset_names:
            print(f"✅ Connexion réussie - Dataset {dataset_id} trouvé")
            
            # Lister les tables
            dataset_ref = client.dataset(dataset_id)
            tables = list(client.list_tables(dataset_ref))
            
            if tables:
                print("📋 Tables existantes :")
                for table in tables:
                    print(f"  - {table.table_id}")
            else:
                print("📋 Aucune table trouvée")
            
            return True
        else:
            print(f"❌ Dataset {dataset_id} introuvable")
            print(f"📋 Datasets disponibles: {', '.join(dataset_names)}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

if __name__ == "__main__":
    test_connection()