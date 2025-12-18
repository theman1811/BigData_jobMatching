# Documentation - Déduplication BigQuery

## 📋 Problème identifié

À chaque exécution du DAG `scraping_daily`, les **mêmes offres d'emploi** étaient scrapées et insérées dans BigQuery, causant :

- ✅ **300 offres uniques** constantes
- ❌ **Nombre total d'offres en augmentation continue** (doublons)
- 💾 **Gaspillage de stockage et données dupliquées**

### Cause racine

1. **job_id stable** : Les offres génèrent toujours le même ID (basé sur URL/titre/entreprise, sans timestamp)
2. **Fichiers HTML écrasés** : MinIO écrase les fichiers avec le même nom (`{job_id}.html`)
3. **Pas de vérification des doublons** : Le script `load_to_bigquery.py` utilisait `mode="append"` sans vérifier l'existence préalable
4. **Déduplication désactivée** : La tâche Spark de déduplication était commentée dans le DAG

---

## ✅ Solution implémentée : Approche A - Déduplication Spark avant insertion

### Principe

Avant chaque insertion dans BigQuery, le script Spark :

1. **Lit les IDs existants** depuis la table BigQuery cible
2. **Effectue un LEFT ANTI JOIN** pour filtrer les doublons
3. **Insère uniquement les nouvelles données**

### Modifications apportées

#### Fichier modifié : `spark/batch/load_to_bigquery.py`

**Changements pour chaque table** (Fact_OffresEmploi, Dim_Entreprise, Dim_Localisation, Dim_Competence) :

```python
# AVANT (insertion sans vérification)
fact_offres_df.write \
    .format("bigquery") \
    .option("table", fact_table) \
    .mode("append") \
    .save()

# APRÈS (déduplication avant insertion)
try:
    # Lire les IDs existants
    existing_offres = spark.read \
        .format("bigquery") \
        .option("table", fact_table) \
        .load() \
        .select("offre_id") \
        .distinct()
    
    # Filtrer les nouvelles offres (LEFT ANTI JOIN)
    new_offres = fact_offres_df.join(
        existing_offres,
        on="offre_id",
        how="left_anti"
    )
    
    # Insérer uniquement les nouvelles
    if new_offres.count() > 0:
        new_offres.write \
            .format("bigquery") \
            .option("table", fact_table) \
            .mode("append") \
            .save()
        print(f"✅ {new_offres.count()} nouvelles offres insérées")
    else:
        print(f"ℹ️ Aucune nouvelle offre à insérer")

except Exception as e:
    # Si la table n'existe pas, créer et insérer toutes les données
    if "Not found: Table" in str(e) or "404" in str(e):
        fact_offres_df.write.format("bigquery").mode("append").save()
```

---

## 📊 Résultats attendus

### Avant la modification

| Exécution | Offres scrapées | Offres insérées | Total BigQuery |
|-----------|-----------------|-----------------|----------------|
| Jour 1    | 300             | 300             | 300            |
| Jour 2    | 300             | 300             | 600 ❌         |
| Jour 3    | 300             | 300             | 900 ❌         |

**Problème** : Toujours 300 offres uniques, mais nombre total augmente sans cesse

### Après la modification

| Exécution | Offres scrapées | Nouvelles offres | Offres insérées | Total BigQuery |
|-----------|-----------------|------------------|-----------------|----------------|
| Jour 1    | 300             | 300              | 300             | 300            |
| Jour 2    | 300             | 15               | 15              | 315 ✅         |
| Jour 3    | 300             | 8                | 8               | 323 ✅         |

**Résultat** : Seules les nouvelles offres sont insérées, pas de doublons

---

## 🚀 Test et validation

### Comment tester

1. **Vider les tables BigQuery** (si nécessaire pour test propre) :
   ```sql
   TRUNCATE TABLE `jobmatching_dw.Fact_OffresEmploi`;
   TRUNCATE TABLE `jobmatching_dw.Dim_Entreprise`;
   TRUNCATE TABLE `jobmatching_dw.Dim_Localisation`;
   TRUNCATE TABLE `jobmatching_dw.Dim_Competence`;
   ```

2. **Exécuter le DAG processing_spark** une première fois :
   ```bash
   # Depuis Airflow UI ou CLI
   airflow dags trigger processing_spark
   ```

3. **Vérifier les logs Spark** :
   - Rechercher : `"📊 Vérification des offres existantes"`
   - Première exécution : `"0 offres existantes trouvées"`
   - Devrait afficher : `"X nouvelles offres à insérer (sur X au total)"`

4. **Compter les offres dans BigQuery** :
   ```sql
   SELECT COUNT(*) as total_offres,
          COUNT(DISTINCT offre_id) as offres_uniques
   FROM `jobmatching_dw.Fact_OffresEmploi`;
   ```
   → **total_offres** doit égaler **offres_uniques**

5. **Réexécuter le DAG** (sans nouveau scraping) :
   ```bash
   airflow dags trigger processing_spark
   ```

6. **Vérifier les logs** :
   - Devrait afficher : `"ℹ️ Aucune nouvelle offre à insérer"`
   - Ou très peu de nouvelles offres si scraping entre-temps

7. **Revérifier BigQuery** :
   ```sql
   SELECT COUNT(*) as total_offres,
          COUNT(DISTINCT offre_id) as offres_uniques
   FROM `jobmatching_dw.Fact_OffresEmploi`;
   ```
   → **total_offres** doit toujours égaler **offres_uniques** ✅

### Métriques de succès

✅ **`total_offres == offres_uniques`** dans toutes les tables  
✅ **Logs affichent** le nombre de nouvelles vs existantes  
✅ **Pas d'augmentation** du total si aucune nouvelle offre  
✅ **Performance acceptable** (lecture index BigQuery rapide)

---

## 🔧 Maintenance future

### Nettoyage des anciennes offres

Pour supprimer les offres expirées/anciennes (>90 jours) :

```sql
DELETE FROM `jobmatching_dw.Fact_OffresEmploi`
WHERE date_publication < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY);
```

### Monitoring des doublons

Query de vérification mensuelle :

```sql
-- Vérifier s'il reste des doublons
SELECT offre_id, COUNT(*) as count
FROM `jobmatching_dw.Fact_OffresEmploi`
GROUP BY offre_id
HAVING COUNT(*) > 1
ORDER BY count DESC;
```

---

## 🎯 Prochaines étapes (optionnelles)

### Option 1 : Réactiver la déduplication Spark inter-sources

Décommenter dans `airflow/dags/processing_spark_dag.py` :

```python
# Lignes 167-171
spark_deduplicate = SparkSubmitOperator(
    task_id='spark_deduplicate',
    application=f"{SPARK_APP_PATH}/deduplicate.py",
    **spark_common_kwargs
)
```

Puis modifier le pipeline pour utiliser `jobs_deduplicated` au lieu de `jobs_parsed`.

**Bénéfice** : Déduplication des offres similaires provenant de sources différentes (ex: même offre sur Educarriere et Macarrierepro).

### Option 2 : Ajouter une table de tracking

Créer une table `Logs_JobTracking` pour tracer les insertions :

```sql
CREATE TABLE IF NOT EXISTS `jobmatching_dw.Logs_JobTracking` (
  offre_id STRING NOT NULL,
  first_seen TIMESTAMP,
  last_seen TIMESTAMP,
  scraped_count INT64,
  source_sites ARRAY<STRING>
);
```

**Bénéfice** : Historique complet de chaque offre (première apparition, fréquence, sources).

---

## 📝 Notes techniques

### Performance

- **LEFT ANTI JOIN** : Efficace car utilise les index BigQuery sur la colonne `offre_id`
- **Lecture selective** : Seules les colonnes nécessaires sont lues (ex: `offre_id` uniquement)
- **Première exécution** : Lente (table n'existe pas), exécutions suivantes : rapides

### Limitations

- **Pas d'UPDATE** : Si une offre existe déjà, elle n'est pas mise à jour (seules les nouvelles sont insérées)
- **Coût BigQuery** : Lecture de la table à chaque exécution (minimisé par lecture selective)

### Alternatives non retenues

1. **MERGE SQL** : Plus complexe, nécessite table staging
2. **Tracking fichiers MinIO** : Ne résout pas le problème des fichiers écrasés
3. **Ajouter timestamp au job_id** : Casse l'unicité logique des offres

---

**Date de création** : 17 décembre 2024  
**Auteur** : Data Team  
**Version** : 1.0
