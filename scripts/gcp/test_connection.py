#!/usr/bin/env python3
"""
Test de connexion à Google Cloud Platform
Vérifie que les credentials et les accès GCS/BigQuery fonctionnent
"""

import os
import sys

def test_gcs():
    """Test Google Cloud Storage"""
    print("🧪 Test GCS (Google Cloud Storage)...")
    try:
        from google.cloud import storage
        
        client = storage.Client()
        buckets = list(client.list_buckets())
        print(f"✅ GCS OK - {len(buckets)} bucket(s) trouvé(s)")
        
        for bucket in buckets:
            print(f"   • {bucket.name} (location: {bucket.location})")
        
        return True
    except ImportError:
        print("❌ Erreur: Module 'google-cloud-storage' non installé")
        print("   Installez avec: pip install google-cloud-storage")
        return False
    except Exception as e:
        print(f"❌ Erreur GCS: {e}")
        print("\n💡 Vérifiez que:")
        print("   1. Le fichier de credentials existe")
        print("   2. La variable GOOGLE_APPLICATION_CREDENTIALS est correcte")
        print("   3. Le Service Account a les permissions Storage Admin")
        return False

def test_bigquery():
    """Test BigQuery"""
    print("\n🧪 Test BigQuery...")
    try:
        from google.cloud import bigquery
        
        client = bigquery.Client()
        datasets = list(client.list_datasets())
        print(f"✅ BigQuery OK - {len(datasets)} dataset(s) trouvé(s)")
        
        for dataset in datasets:
            print(f"   • {dataset.dataset_id}")
        
        # Test de query simple
        query = "SELECT 1 as test"
        result = client.query(query).result()
        print("✅ Query de test exécutée avec succès")
        
        return True
    except ImportError:
        print("❌ Erreur: Module 'google-cloud-bigquery' non installé")
        print("   Installez avec: pip install google-cloud-bigquery")
        return False
    except Exception as e:
        print(f"❌ Erreur BigQuery: {e}")
        print("\n💡 Vérifiez que:")
        print("   1. Le fichier de credentials existe")
        print("   2. La variable GOOGLE_APPLICATION_CREDENTIALS est correcte")
        print("   3. Le Service Account a les permissions BigQuery Admin")
        return False

def check_credentials():
    """Vérifier que les credentials sont configurés"""
    print("🔑 Vérification des credentials...\n")
    
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not cred_path:
        print("⚠️  Variable GOOGLE_APPLICATION_CREDENTIALS non définie")
        print("\n💡 Solution:")
        print("   export GOOGLE_APPLICATION_CREDENTIALS='./credentials/gcp-service-account.json'")
        print("   Ou ajoutez-la dans votre fichier config.env")
        return False
    
    if not os.path.exists(cred_path):
        print(f"❌ Fichier de credentials introuvable: {cred_path}")
        print("\n💡 Vérifiez que vous avez bien téléchargé la clé JSON du Service Account")
        return False
    
    print(f"✅ Credentials trouvés: {cred_path}\n")
    return True

def main():
    """Fonction principale"""
    print("="*60)
    print("🔍 TEST DE CONNEXION GOOGLE CLOUD PLATFORM")
    print("="*60)
    print()
    
    # Vérifier les credentials
    if not check_credentials():
        sys.exit(1)
    
    # Tests
    print("-"*60)
    gcs_ok = test_gcs()
    bq_ok = test_bigquery()
    print("-"*60)
    
    # Résumé
    print("\n" + "="*60)
    if gcs_ok and bq_ok:
        print("✅ TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
        print("\n🎉 Votre configuration GCP est prête à l'emploi.")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("\n📖 Consultez le guide: docs/setup_gcp.md")
        sys.exit(1)
    print("="*60)

if __name__ == "__main__":
    main()

