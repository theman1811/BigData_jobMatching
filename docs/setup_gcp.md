# ☁️ Guide de Configuration GCP

Ce guide vous accompagne dans la configuration de votre compte Google Cloud Platform pour le projet BigData OrangeScrum.

## 🎓 Étape 1 : Obtenir les Crédits Étudiants

### Programme Google Cloud for Education

1. **Accéder au programme étudiant** :
   - URL : https://cloud.google.com/edu
   - Ou : https://edu.google.com/programs/credits/

2. **Vérifier votre éligibilité** :
   - Adresse email universitaire (@*.edu ou email étudiant)
   - Inscription dans un établissement reconnu

3. **Créer votre compte** :
   - Si vous avez déjà un compte Google, utilisez-le
   - Sinon, créez un nouveau compte Gmail

4. **Obtenir les crédits** :
   - **Option 1** : 300$ de crédits gratuits (nouveau compte GCP)
     - Valable 90 jours
     - Aucune carte bancaire requise (version étudiante)
   
   - **Option 2** : Programme éducatif spécifique
     - Varie selon l'établissement
     - Demander à votre professeur s'il existe un programme

## 🚀 Étape 2 : Créer un Projet GCP

### 2.1 Accéder à la Console GCP

1. Se connecter à : https://console.cloud.google.com
2. Accepter les conditions d'utilisation

### 2.2 Créer un Nouveau Projet

1. Cliquer sur le sélecteur de projet (en haut)
2. Cliquer sur "Nouveau projet"
3. Remplir les informations :
   ```
   Nom du projet : bigdata-orangescrum
   ID du projet : bigdata-orangescrum-[random]
   Organisation : Aucune organisation
   ```
4. Cliquer sur "Créer"

### 2.3 Activer la Facturation (si nécessaire)

1. Menu ≡ → "Facturation"
2. Lier le projet à votre compte de facturation
3. Avec les crédits étudiants, aucun paiement ne sera effectué

## 🔑 Étape 3 : Créer un Service Account

### 3.1 Pourquoi un Service Account ?

Le Service Account permet à vos applications locales (Spark, Airflow) de s'authentifier sur GCP.

### 3.2 Création

1. **Accéder à IAM** :
   - Menu ≡ → "IAM et administration" → "Comptes de service"

2. **Créer le Service Account** :
   - Cliquer sur "+ CRÉER UN COMPTE DE SERVICE"
   - Nom : `bigdata-orangescrum-sa`
   - Description : `Service account pour le projet BigData`
   - Cliquer sur "Créer et continuer"

3. **Attribuer les rôles** :
   - Ajouter les rôles suivants :
     ```
     • Storage Admin (pour GCS)
     • BigQuery Admin (pour BigQuery)
     • BigQuery Data Editor (pour écrire des données)
     • BigQuery Job User (pour lancer des queries)
     ```
   - Cliquer sur "Continuer"

4. **Finaliser** :
   - Cliquer sur "Terminé"

### 3.3 Télécharger la Clé JSON

1. Dans la liste des comptes de service, trouver `bigdata-orangescrum-sa`
2. Cliquer sur les trois points → "Gérer les clés"
3. "Ajouter une clé" → "Créer une clé"
4. Type : JSON
5. Cliquer sur "Créer"
6. La clé se télécharge automatiquement

⚠️ **IMPORTANT** : Cette clé donne accès à votre projet. Ne la commitez JAMAIS dans Git !

### 3.4 Configurer la Clé Localement

```bash
# Créer un dossier pour les credentials
cd /Users/apple/Documents/programmation/school/bigData_orangeScrum
mkdir -p credentials

# Déplacer la clé téléchargée
mv ~/Downloads/bigdata-orangescrum-*.json credentials/gcp-service-account.json

# Vérifier
ls credentials/
```

## 🪣 Étape 4 : Créer un Bucket GCS (Data Lake)

### 4.1 Activer l'API Cloud Storage

1. Menu ≡ → "APIs et services" → "Bibliothèque"
2. Rechercher "Cloud Storage"
3. Cliquer sur "Cloud Storage API"
4. Cliquer sur "Activer"

### 4.2 Créer le Bucket

1. **Via la Console** :
   - Menu ≡ → "Cloud Storage" → "Buckets"
   - Cliquer sur "+ CRÉER"
   - Configuration :
     ```
     Nom : orangescrum-datalake-[votre-id-unique]
     Type d'emplacement : Région
     Région : europe-west1 (Belgique)
     Classe de stockage : Standard
     Contrôle d'accès : Uniforme
     Protection : Aucune (pour l'instant)
     ```
   - Cliquer sur "Créer"

2. **Via la CLI** (alternatif) :
   ```bash
   gcloud storage buckets create gs://orangescrum-datalake-unique \
     --location=europe-west1 \
     --uniform-bucket-level-access
   ```

### 4.3 Créer la Structure du Bucket

```bash
# Créer des dossiers virtuels
gsutil mkdir gs://orangescrum-datalake-unique/raw/
gsutil mkdir gs://orangescrum-datalake-unique/processed/
gsutil mkdir gs://orangescrum-datalake-unique/archive/
```

## 📊 Étape 5 : Configurer BigQuery

### 5.1 Activer l'API BigQuery

1. Menu ≡ → "APIs et services" → "Bibliothèque"
2. Rechercher "BigQuery"
3. Cliquer sur "BigQuery API"
4. Cliquer sur "Activer"

### 5.2 Créer un Dataset

1. **Via la Console** :
   - Menu ≡ → "BigQuery" → "BigQuery Studio"
   - Dans le panneau de gauche, cliquer sur votre projet
   - Cliquer sur les trois points → "Créer un ensemble de données"
   - Configuration :
     ```
     ID de l'ensemble de données : orangescrum_dw
     Emplacement : EU (multi-régions)
     Expiration des tables par défaut : Jamais
     Chiffrement : Clé gérée par Google
     ```
   - Cliquer sur "Créer un ensemble de données"

2. **Via la CLI** (alternatif) :
   ```bash
   bq mk --location=EU orangescrum_dw
   ```

### 5.3 Créer une Table de Test

```sql
-- Dans l'éditeur BigQuery, exécuter :
CREATE TABLE `orangescrum_dw.test_table` (
  id INT64,
  name STRING,
  created_at TIMESTAMP
)
PARTITION BY DATE(created_at);

-- Insérer des données de test
INSERT INTO `orangescrum_dw.test_table` (id, name, created_at)
VALUES 
  (1, 'Test 1', CURRENT_TIMESTAMP()),
  (2, 'Test 2', CURRENT_TIMESTAMP());

-- Vérifier
SELECT * FROM `orangescrum_dw.test_table`;
```

## 🔧 Étape 6 : Configuration Locale

### 6.1 Mettre à Jour config.env

```bash
# Éditer le fichier config.env
nano config.env
```

Modifier les valeurs GCP :
```bash
# ==============================================
# GCP Configuration
# ==============================================
GCP_PROJECT_ID=bigdata-orangescrum-123456
GCP_REGION=europe-west1
GCS_BUCKET_NAME=orangescrum-datalake-unique
BIGQUERY_DATASET=orangescrum_dw
GOOGLE_APPLICATION_CREDENTIALS=./credentials/gcp-service-account.json
```

### 6.2 Installer le Google Cloud SDK (optionnel)

**Sur macOS** :
```bash
# Avec Homebrew
brew install --cask google-cloud-sdk

# Initialiser
gcloud init

# Se connecter
gcloud auth login

# Configurer le projet
gcloud config set project bigdata-orangescrum-123456
```

**Sur Linux** :
```bash
# Télécharger et installer
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

### 6.3 Tester la Connexion

#### Test GCS

```bash
# Créer un fichier de test
echo "Hello GCS!" > test.txt

# Uploader
gsutil cp test.txt gs://orangescrum-datalake-unique/

# Lister
gsutil ls gs://orangescrum-datalake-unique/

# Supprimer le test
gsutil rm gs://orangescrum-datalake-unique/test.txt
rm test.txt
```

#### Test BigQuery

```bash
# Lister les datasets
bq ls

# Lister les tables
bq ls orangescrum_dw

# Query de test
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as total FROM `orangescrum_dw.test_table`'
```

## 📈 Étape 7 : Configurer les Alertes de Facturation

### 7.1 Créer un Budget

1. Menu ≡ → "Facturation" → "Budgets et alertes"
2. Cliquer sur "Créer un budget"
3. Configuration :
   ```
   Nom : Budget Projet BigData
   Projets : bigdata-orangescrum-123456
   Montant : 10 EUR (ou votre limite souhaitée)
   ```
4. Alertes :
   ```
   50% du budget : Email
   90% du budget : Email
   100% du budget : Email
   ```
5. Cliquer sur "Terminer"

### 7.2 Surveiller les Coûts

```bash
# Via CLI
gcloud billing accounts list
gcloud billing projects describe bigdata-orangescrum-123456

# Via Console
Menu ≡ → Facturation → Rapports
```

## 🎨 Étape 8 : Configurer Looker Studio

### 8.1 Accéder à Looker Studio

1. URL : https://lookerstudio.google.com
2. Se connecter avec le même compte Google

### 8.2 Créer une Source de Données

1. Cliquer sur "Créer" → "Source de données"
2. Sélectionner "BigQuery"
3. Autoriser l'accès
4. Sélectionner :
   ```
   Projet : bigdata-orangescrum-123456
   Dataset : orangescrum_dw
   Table : test_table (pour commencer)
   ```
5. Cliquer sur "Connecter"

### 8.3 Créer un Premier Dashboard (Test)

1. Cliquer sur "Créer" → "Rapport"
2. Sélectionner la source de données créée
3. Ajouter un graphique de test
4. Cliquer sur "Ajouter au rapport"

## ✅ Étape 9 : Vérification Complète

### Checklist

- [ ] Compte GCP créé avec crédits
- [ ] Projet `bigdata-orangescrum` créé
- [ ] Service Account créé avec les bons rôles
- [ ] Clé JSON téléchargée et placée dans `credentials/`
- [ ] Bucket GCS créé : `orangescrum-datalake-*`
- [ ] Dataset BigQuery créé : `orangescrum_dw`
- [ ] Table de test créée et fonctionnelle
- [ ] `config.env` mis à jour avec les bonnes valeurs
- [ ] Google Cloud SDK installé (optionnel)
- [ ] Tests de connexion GCS réussis
- [ ] Tests de connexion BigQuery réussis
- [ ] Budget et alertes configurés
- [ ] Looker Studio connecté à BigQuery

### Script de Test Complet

Créer un fichier `scripts/gcp/test_connection.py` :

```python
#!/usr/bin/env python3
"""Test de connexion à GCP"""

import os
from google.cloud import storage, bigquery

# Charger les credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './credentials/gcp-service-account.json'

def test_gcs():
    """Test Google Cloud Storage"""
    print("🧪 Test GCS...")
    try:
        client = storage.Client()
        buckets = list(client.list_buckets())
        print(f"✅ GCS OK - {len(buckets)} bucket(s) trouvé(s)")
        for bucket in buckets:
            print(f"   • {bucket.name}")
        return True
    except Exception as e:
        print(f"❌ GCS Error: {e}")
        return False

def test_bigquery():
    """Test BigQuery"""
    print("\n🧪 Test BigQuery...")
    try:
        client = bigquery.Client()
        datasets = list(client.list_datasets())
        print(f"✅ BigQuery OK - {len(datasets)} dataset(s) trouvé(s)")
        for dataset in datasets:
            print(f"   • {dataset.dataset_id}")
        return True
    except Exception as e:
        print(f"❌ BigQuery Error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Test de connexion GCP\n")
    gcs_ok = test_gcs()
    bq_ok = test_bigquery()
    
    print("\n" + "="*50)
    if gcs_ok and bq_ok:
        print("✅ Tous les tests sont OK!")
    else:
        print("❌ Certains tests ont échoué")
```

Exécuter :
```bash
python3 scripts/gcp/test_connection.py
```

## 🆘 Dépannage

### Erreur : "Permission Denied"

**Solution** :
1. Vérifier que le Service Account a les bons rôles
2. Vérifier que `GOOGLE_APPLICATION_CREDENTIALS` pointe vers le bon fichier
3. Re-télécharger la clé JSON si nécessaire

### Erreur : "Quota Exceeded"

**Solution** :
1. Vérifier les quotas : Menu ≡ → "IAM" → "Quotas"
2. Demander une augmentation si nécessaire (généralement pas nécessaire en mode gratuit)

### Bucket déjà existant

**Solution** :
- Les noms de buckets GCS sont uniques globalement
- Ajouter un suffixe unique : `orangescrum-datalake-votreprenom`

## 📚 Ressources

- [GCP Free Tier](https://cloud.google.com/free)
- [GCP for Students](https://cloud.google.com/edu)
- [BigQuery Sandbox](https://cloud.google.com/bigquery/docs/sandbox)
- [GCS Documentation](https://cloud.google.com/storage/docs)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)

---

**Prochaine étape** : Retour au README principal pour démarrer la plateforme locale !

