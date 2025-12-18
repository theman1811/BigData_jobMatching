#!/usr/bin/env python3
"""
Test de déduplication BigQuery
Vérifie que les offres ne sont pas dupliquées lors de l'insertion
"""

import os
import sys
from google.cloud import bigquery
from google.oauth2 import service_account

# Configuration
PROJECT_ID = "bigdata-jobmatching-test"
DATASET_ID = "jobmatching_dw"
CREDENTIALS_PATH = "/Users/nedio/Documents/programmation/school/BigData_jobMatching/credentials/bq-service-account.json"

def get_bigquery_client():
    """Crée un client BigQuery"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        return client
    except Exception as e:
        print(f"❌ Erreur connexion BigQuery: {e}")
        return None

def check_table_stats(client, table_name):
    """Vérifie les statistiques d'une table"""
    query = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT {table_name.split('_')[1].lower()}_id) as unique_ids
    FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
    """
    
    try:
        result = client.query(query).result()
        row = list(result)[0]
        return {
            "total": row.total_rows,
            "unique": row.unique_ids,
            "has_duplicates": row.total_rows != row.unique_ids
        }
    except Exception as e:
        if "Not found" in str(e):
            print(f"⚠️  Table {table_name} n'existe pas encore")
            return {"total": 0, "unique": 0, "has_duplicates": False}
        else:
            print(f"❌ Erreur: {e}")
            return None

def check_duplicate_offre_ids(client):
    """Liste les offre_id dupliqués"""
    query = f"""
    SELECT offre_id, COUNT(*) as count
    FROM `{PROJECT_ID}.{DATASET_ID}.Fact_OffresEmploi`
    GROUP BY offre_id
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 10
    """
    
    try:
        result = client.query(query).result()
        duplicates = list(result)
        if duplicates:
            print("\n⚠️  Offres dupliquées détectées:")
            for row in duplicates:
                print(f"   - {row.offre_id}: {row.count} fois")
        return len(duplicates)
    except Exception as e:
        if "Not found" in str(e):
            return 0
        else:
            print(f"❌ Erreur: {e}")
            return -1

def main():
    """Fonction principale de test"""
    print("=" * 60)
    print("🧪 TEST DE DÉDUPLICATION BIGQUERY")
    print("=" * 60)
    
    # Connexion BigQuery
    client = get_bigquery_client()
    if not client:
        print("❌ Impossible de se connecter à BigQuery")
        sys.exit(1)
    
    print("✅ Connexion BigQuery établie\n")
    
    # Tables à vérifier
    tables = [
        "Fact_OffresEmploi",
        "Dim_Entreprise",
        "Dim_Localisation",
        "Dim_Competence"
    ]
    
    # Vérifier chaque table
    print("📊 STATISTIQUES DES TABLES\n")
    all_clean = True
    
    for table in tables:
        print(f"📋 {table}:")
        stats = check_table_stats(client, table)
        
        if stats:
            print(f"   Total de lignes: {stats['total']}")
            print(f"   IDs uniques: {stats['unique']}")
            
            if stats['has_duplicates']:
                print(f"   ❌ DOUBLONS DÉTECTÉS ! ({stats['total'] - stats['unique']} doublons)")
                all_clean = False
            else:
                print(f"   ✅ Aucun doublon")
        print()
    
    # Vérifier les doublons spécifiques dans Fact_OffresEmploi
    print("🔍 RECHERCHE DE DOUBLONS SPÉCIFIQUES\n")
    duplicate_count = check_duplicate_offre_ids(client)
    
    if duplicate_count == 0:
        print("✅ Aucun doublon détecté dans Fact_OffresEmploi\n")
    elif duplicate_count > 0:
        print(f"⚠️  {duplicate_count} offre_id avec doublons\n")
        all_clean = False
    
    # Résumé final
    print("=" * 60)
    if all_clean:
        print("✅ SUCCÈS : Toutes les tables sont propres (pas de doublons)")
        print("=" * 60)
        return 0
    else:
        print("❌ ÉCHEC : Des doublons ont été détectés")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
