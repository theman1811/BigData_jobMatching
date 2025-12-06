# SQL et Charts Superset - Dashboards Marché de l’Emploi

Guide rapide des métriques par dashboard, avec type de chart Superset et requêtes BigQuery (standard SQL). Adapter `@date_deb` / `@date_fin` selon vos filtres.

---

## Dashboard 1 — Vue d’Ensemble (macro)
- Big Number : Total d’offres  
```sql
SELECT SUM(offres_totales) AS total_offres
FROM `jobmatching_dw.v_offres_daily`
WHERE date_publication BETWEEN @date_deb AND @date_fin;
```
- Big Number : Offres uniques  
```sql
SELECT SUM(offres_uniques) AS offres_uniques
FROM `jobmatching_dw.v_offres_daily`
WHERE date_publication BETWEEN @date_deb AND @date_fin;
```
- Big Number : Variation % (semaine/mois)  
```sql
WITH cur AS (
  SELECT SUM(offres_totales) v FROM `jobmatching_dw.v_offres_daily`
  WHERE date_publication BETWEEN @date_deb AND @date_fin
), prev AS (
  SELECT SUM(offres_totales) v FROM `jobmatching_dw.v_offres_daily`
  WHERE date_publication BETWEEN DATE_SUB(@date_deb, INTERVAL 7 DAY) AND DATE_SUB(@date_fin, INTERVAL 7 DAY)
)
SELECT SAFE_DIVIDE(cur.v - prev.v, prev.v) AS var_pct FROM cur, prev;
```
- Big Number/KPI : Salaires min/max moyens  
```sql
SELECT AVG(salaire_min_moy) AS salaire_min_moy, AVG(salaire_max_moy) AS salaire_max_moy
FROM `jobmatching_dw.v_offres_daily`
WHERE date_publication BETWEEN @date_deb AND @date_fin;
```
- Line Chart : Évolution temporelle des offres  
```sql
SELECT date_publication, SUM(offres_totales) AS offres_totales
FROM `jobmatching_dw.v_offres_daily`
GROUP BY date_publication
ORDER BY date_publication;
```
- Line Chart : Évolution salaires moyens  
```sql
SELECT date_publication,
       AVG(salaire_min_moy) AS salaire_min_moy,
       AVG(salaire_max_moy) AS salaire_max_moy
FROM `jobmatching_dw.v_offres_daily`
GROUP BY date_publication
ORDER BY date_publication;
```

---

## Dashboard 2 — Analyse Sectorielle
- Bar Chart : Top secteurs qui recrutent  
```sql
SELECT nom_secteur, offres_totales
FROM `jobmatching_dw.v_salaires_secteur`
ORDER BY offres_totales DESC
LIMIT 10;
```
- Bar/Big Number : Salaire médian par secteur  
```sql
SELECT nom_secteur, salaire_min_p50, salaire_max_p50
FROM `jobmatching_dw.v_salaires_secteur`;
```
- Stacked Bar / Heatmap : Contrats dominants par secteur  
```sql
SELECT se.nom_secteur, fe.type_contrat, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2;
```
- Bar / Heatmap : Niveau d’expérience par secteur  
```sql
SELECT se.nom_secteur, fe.niveau_experience, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2
ORDER BY n DESC;
```
- Box Plot : Salaires par secteur (p10/p50/p90)  
```sql
SELECT nom_secteur,
       salaire_min_p10, salaire_min_p50, salaire_min_p90,
       salaire_max_p50
FROM `jobmatching_dw.v_salaires_secteur`;
```
- Heatmap (Secteur × Type de contrat)  
```sql
SELECT se.nom_secteur, fe.type_contrat, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2;
```

---

## Dashboard 3 — Analyse Géographique
- Bar Chart : Top villes / régions  
```sql
SELECT lo.ville, lo.region, COUNT(*) AS offres_totales
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Localisation` lo ON fe.localisation_id = lo.localisation_id
GROUP BY 1,2
ORDER BY offres_totales DESC
LIMIT 20;
```
- Bar / Table : Salaires moyens par zone  
```sql
SELECT ville, secteur, salaire_min_moy, salaire_max_moy, salaire_min_p50, salaire_max_p50
FROM `jobmatching_dw.v_salaires_secteur_ville`;
```
- Bar / Heatmap : Secteurs dominants par ville/région  
```sql
SELECT lo.ville, lo.region, se.nom_secteur, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Localisation` lo ON fe.localisation_id = lo.localisation_id
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2,3
ORDER BY n DESC;
```
- Heatmap (ville × secteur)  
```sql
SELECT lo.ville, se.nom_secteur, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Localisation` lo ON fe.localisation_id = lo.localisation_id
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2;
```

---

## Dashboard 4 — Types de Contrat & Télétravail
- Pie / Bar : Répartition des types de contrat  
```sql
SELECT type_contrat, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi`
GROUP BY 1;
```
- Bar / KPI : Taux de télétravail par secteur  
```sql
SELECT nom_secteur, part_teletravail, taux_teletravail_moy, taux_teletravail_p50, taux_teletravail_p90
FROM `jobmatching_dw.v_teletravail_secteur`;
```
- Histogramme : Distribution du % télétravail  
```sql
SELECT
  CAST(FLOOR(taux_teletravail/10)*10 AS INT64) AS bin_pct,
  COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi`
WHERE taux_teletravail IS NOT NULL
GROUP BY bin_pct
ORDER BY bin_pct;
```
- Stacked Bar : Contrats × secteurs  
```sql
SELECT se.nom_secteur, fe.type_contrat, COUNT(*) AS n
FROM `jobmatching_dw.Fact_OffresEmploi` fe
LEFT JOIN `jobmatching_dw.Dim_Secteur` se ON fe.secteur_id = se.secteur_id
GROUP BY 1,2;
```

---

## Dashboard 5 — Compétences les Plus Demandées
- Bar / Word Cloud : Top compétences globales  
```sql
SELECT competence, SUM(occurrences) AS occ_total
FROM `jobmatching_dw.v_top_competences`
GROUP BY competence
ORDER BY occ_total DESC
LIMIT 20;
```
- Heatmap : Compétence × Secteur  
```sql
SELECT competence, secteur_id, SUM(occurrences) AS occ_total
FROM `jobmatching_dw.v_top_competences`
GROUP BY 1,2;
```
- Word Cloud (poids = occ_total)  
```sql
SELECT competence, SUM(occurrences) AS occ_total
FROM `jobmatching_dw.v_top_competences`
GROUP BY competence;
```
- Bar / Table : Compétences par localisation  
```sql
SELECT localisation_id, competence, SUM(occurrences) AS occ_total
FROM `jobmatching_dw.v_top_competences`
GROUP BY 1,2
ORDER BY occ_total DESC;
```

---

## Dashboard 6 — Supervision des Pipelines
- Big Number : Volume total records ingérés  
```sql
SELECT SUM(records_processed) AS records_totaux
FROM `jobmatching_dw.Logs_Processing`
WHERE DATE(start_time) BETWEEN @date_deb AND @date_fin;
```
- Bar / Pie : Succès vs échecs (par job ou global)  
```sql
SELECT job_name, statut, COUNT(*) AS runs
FROM `jobmatching_dw.Logs_Processing`
GROUP BY 1,2;
```
- Bar : Temps moyen d’exécution par job  
```sql
SELECT job_name, AVG(duration_seconds) AS duree_moy_s
FROM `jobmatching_dw.Logs_Processing`
GROUP BY 1;
```
- Bar : Jobs les plus coûteux CPU / RAM  
```sql
SELECT job_name,
       AVG(cpu_time_seconds) AS cpu_moy_s,
       AVG(memory_used_mb)   AS mem_moy_mb
FROM `jobmatching_dw.Logs_Processing`
GROUP BY 1
ORDER BY cpu_moy_s DESC, mem_moy_mb DESC;
```
- Line : Logs quotidiens (records traités)  
```sql
SELECT DATE(start_time) AS date, SUM(records_processed) AS records_totaux
FROM `jobmatching_dw.Logs_Processing`
GROUP BY date
ORDER BY date;
```
- Bar : Erreurs par job_type  
```sql
SELECT job_type, COUNT(*) AS erreurs
FROM `jobmatching_dw.Logs_Processing`
WHERE statut != 'SUCCESS'
GROUP BY 1;
```

