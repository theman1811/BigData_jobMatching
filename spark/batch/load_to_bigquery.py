#!/usr/bin/env python3
"""
==========================================
Spark Batch - Load to BigQuery
==========================================
Job Spark Batch pour charger les données traitées vers BigQuery.

Source: s3a://processed-data/jobs_parsed/
Destination: BigQuery (Fact_OffresEmploi, dimensions)
"""

import os
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, when, coalesce, concat, md5, to_date,
    current_timestamp, date_format, explode, arrays_zip,
    array_distinct, size, expr, concat_ws, regexp_replace,
    trim, lower, upper, year, month, dayofmonth
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType,
    BooleanType, ArrayType, DateType, TimestampType
)
from pyspark.sql.window import Window

# Import pour le logging
from logging_utils import write_processing_log


def create_spark_session():
    """Crée la session Spark avec configuration BigQuery"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return SparkSession.builder \
        .appName("BigQueryLoader") \
        .master(spark_master) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.jars.packages",
                "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2") \
        .getOrCreate()


def generate_entreprise_id(company_name):
    """Génère un ID déterministe pour l'entreprise"""
    if not company_name or company_name == "Entreprise confidentielle":
        return "ENT_CONFIDENTIELLE"
    # Nettoyer et créer un hash déterministe
    clean_name = company_name.upper().replace(" ", "").replace("-", "").replace(".", "")
    return f"ENT_{clean_name[:10]}"


def generate_localisation_id(location):
    """Génère un ID déterministe pour la localisation"""
    if not location:
        return "LOC_COTE_DIVOIRE"

    # Mapping des villes ivoiriennes
    city_mapping = {
        "ABIDJAN": "LOC_ABIDJAN",
        "BOUAKE": "LOC_BOUAKE",
        "DABOU": "LOC_DABOU",
        "DALOA": "LOC_DALOA",
        "YAMOUSSOUKRO": "LOC_YAMOUSSOUKRO",
        "SAN-PEDRO": "LOC_SAN_PEDRO",
        "KORHOGO": "LOC_KORHOGO",
        "MAN": "LOC_MAN",
        "GAGNOA": "LOC_GAGNOA",
        "DIVO": "LOC_DIVO",
        "SOUBRE": "LOC_SOUBRE"
    }

    clean_location = location.upper().strip()
    return city_mapping.get(clean_location, f"LOC_{clean_location[:15].replace(' ', '_')}")


def generate_competence_id(skill_name):
    """Génère un ID déterministe pour la compétence"""
    if not skill_name:
        return None
    clean_skill = skill_name.lower().replace(" ", "_").replace("-", "_")
    return f"COMP_{clean_skill[:20]}"


def generate_competence_ids_array(skills_array):
    """Génère un array d'IDs de compétences depuis un array de noms"""
    if not skills_array:
        return []
    return [generate_competence_id(skill) for skill in skills_array if skill]


def parse_salary_amount(salary_text):
    """Parse le montant salarial depuis le texte"""
    if not salary_text:
        return None

    import re

    # Patterns pour extraire les montants
    patterns = [
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:FCFA|CFA|XOF)',
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:€|\$)',
        r'salaire\s*:?\s*(\d+(?:[\s\.,]\d+)*)',
        r'(\d+(?:[\s\.,]\d+)*)\s*(?:par|\/)\s*(?:mois|month)'
    ]

    for pattern in patterns:
        match = re.search(pattern, salary_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(' ', '').replace(',', '').replace('.', '')
            try:
                # Retourner un float pour correspondre au schéma BigQuery FLOAT64
                return float(amount_str)
            except ValueError:
                continue

    return None


def infer_experience_level(title, description):
    """Déduit le niveau d'expérience depuis le titre et description"""
    text = f"{title} {description or ''}".lower()

    # Mappings d'expérience
    if any(word in text for word in ['junior', 'debutant', 'stagiaire', 'entry', '0-2', '0-3']):
        return 'Débutant'
    elif any(word in text for word in ['senior', 'expert', 'lead', 'principal', 'chef', '5+', '10+']):
        return 'Senior'
    elif any(word in text for word in ['intermediaire', 'confirme', '3-5', 'mid-level']):
        return 'Intermédiaire'
    else:
        return 'Non spécifié'


def process_bigquery_load(spark, input_path, bigquery_dataset, gcp_project_id):
    """
    Charge les données vers BigQuery

    Args:
        spark: SparkSession
        input_path: Chemin MinIO source (peut être jobs_parsed ou jobs_enriched_sectors)
        bigquery_dataset: Dataset BigQuery
        gcp_project_id: Projet GCP
    """

    print(f"📖 Lecture des données depuis {input_path}")

    # Lire les données parsées (ou enrichies avec secteurs)
    try:
        jobs_df = spark.read.parquet(input_path)
        total_jobs = jobs_df.count()
        print(f"✅ {total_jobs} offres lues depuis MinIO")
    except Exception as e:
        print(f"⚠️ Erreur lecture depuis {input_path}: {e}")
        # Fallback sur jobs_parsed si jobs_enriched_sectors n'existe pas
        fallback_path = input_path.replace("jobs_enriched_sectors", "jobs_parsed")
        print(f"🔄 Tentative avec chemin de secours: {fallback_path}")
        jobs_df = spark.read.parquet(fallback_path)
        total_jobs = jobs_df.count()
        print(f"✅ {total_jobs} offres lues depuis chemin de secours")

    # Enregistrer les UDFs
    spark.udf.register("generate_entreprise_id", generate_entreprise_id, StringType())
    spark.udf.register("generate_localisation_id", generate_localisation_id, StringType())
    spark.udf.register("generate_competence_id", generate_competence_id, StringType())
    spark.udf.register("generate_competence_ids_array", generate_competence_ids_array, ArrayType(StringType()))
    spark.udf.register("parse_salary_amount", parse_salary_amount, FloatType())
    spark.udf.register("infer_experience_level", infer_experience_level, StringType())

    print("✅ UDFs enregistrées")

    # ============================================
    # PRÉPARATION DES DONNÉES POUR BIGQUERY
    # ============================================

    # Transformer les données pour Fact_OffresEmploi
    # IMPORTANT: Utiliser secteur_id depuis les données si disponible, sinon SECT_INCONNU
    fact_offres_df = jobs_df \
        .withColumn("offre_id", col("job_id")) \
        .withColumn("titre_poste", trim(col("title"))) \
        .withColumn("entreprise_id",
                   expr("generate_entreprise_id(company)")) \
        .withColumn("localisation_id",
                   expr("generate_localisation_id(location)")) \
        .withColumn("secteur_id", 
                   coalesce(col("secteur_id"), lit("SECT_INCONNU"))) \
        .withColumn("type_contrat", col("contract_type")) \
        .withColumn("niveau_experience",
                   expr("infer_experience_level(title, description)")) \
        .withColumn("teletravail", lit(False).cast(BooleanType())) \
        .withColumn("taux_teletravail", lit(0).cast(IntegerType())) \
        .withColumn("salaire_min",
                   expr("parse_salary_amount(parsed_salary_text)").cast(FloatType())) \
        .withColumn("salaire_max",
                   expr("parse_salary_amount(parsed_salary_text)").cast(FloatType())) \
        .withColumn("devise", lit("FCFA")) \
        .withColumn("competences", col("skills")) \
        .withColumn("competences_ids",
                   expr("generate_competence_ids_array(skills)")) \
        .withColumn("source_site", col("source")) \
        .withColumn("url_offre", lit(None).cast(StringType())) \
        .withColumn("date_publication", to_date(col("parsed_at"))) \
        .withColumn("date_expiration", lit(None).cast(DateType())) \
        .withColumn("scraped_at", col("parsed_at").cast(TimestampType())) \
        .withColumn("last_updated", current_timestamp()) \
        .withColumn("statut", lit("ACTIVE")) \
        .withColumn("nombre_vues", lit(0).cast(IntegerType())) \
        .withColumn("nombre_candidatures", lit(0).cast(IntegerType())) \
        .select(
            "offre_id",
            "titre_poste",
            "entreprise_id",
            "localisation_id",
            "secteur_id",
            "type_contrat",
            "niveau_experience",
            "teletravail",
            "taux_teletravail",
            "salaire_min",
            "salaire_max",
            "devise",
            "competences",
            "competences_ids",
            "source_site",
            "url_offre",
            "date_publication",
            "date_expiration",
            "scraped_at",
            "last_updated",
            "statut",
            "nombre_vues",
            "nombre_candidatures"
        )

    print("✅ Données Fact_OffresEmploi préparées")

    # ============================================
    # DIMENSION ENTREPRISE
    # ============================================

    dim_entreprise_df = jobs_df \
        .select("company") \
        .distinct() \
        .withColumn("entreprise_id", expr("generate_entreprise_id(company)")) \
        .withColumn("nom_entreprise", col("company")) \
        .withColumn("secteur_id", lit("SECT_INCONNU")) \
        .withColumn("taille_entreprise", lit("Non spécifiée")) \
        .withColumn("site_web", lit(None).cast(StringType())) \
        .withColumn("created_at", current_timestamp()) \
        .withColumn("updated_at", current_timestamp()) \
        .filter(col("company").isNotNull()) \
        .dropDuplicates(["entreprise_id"]) \
        .select(
            "entreprise_id",
            "nom_entreprise",
            "secteur_id",
            "taille_entreprise",
            "site_web",
            "created_at",
            "updated_at"
        )

    print("✅ Données Dim_Entreprise préparées")

    # ============================================
    # DIMENSION LOCALISATION
    # ============================================

    dim_localisation_df = jobs_df \
        .select("location") \
        .distinct() \
        .withColumn("localisation_id", expr("generate_localisation_id(location)")) \
        .withColumn("ville", col("location")) \
        .withColumn("code_postal", lit(None).cast(StringType())) \
        .withColumn("region", lit("Côte d'Ivoire")) \
        .withColumn("departement", lit(None).cast(StringType())) \
        .withColumn("pays", lit("Côte d'Ivoire")) \
        .withColumn("latitude", lit(None).cast(FloatType())) \
        .withColumn("longitude", lit(None).cast(FloatType())) \
        .withColumn("created_at", current_timestamp()) \
        .filter(col("location").isNotNull()) \
        .dropDuplicates(["localisation_id"]) \
        .select(
            "localisation_id",
            "ville",
            "code_postal",
            "region",
            "departement",
            "pays",
            "latitude",
            "longitude",
            "created_at"
        )

    print("✅ Données Dim_Localisation préparées")

    # ============================================
    # DIMENSION COMPÉTENCE
    # ============================================

    # Exploser les compétences pour créer une ligne par compétence
    skills_exploded_df = jobs_df \
        .select("skills") \
        .filter(col("skills").isNotNull()) \
        .withColumn("skill", explode(col("skills"))) \
        .select("skill") \
        .distinct()

    dim_competence_df = skills_exploded_df \
        .withColumn("competence_id", expr("generate_competence_id(skill)")) \
        .withColumn("nom_competence", col("skill")) \
        .withColumn("categorie", lit("Technique")) \
        .withColumn("niveau_demande", lit("Non spécifié")) \
        .withColumn("popularite_score", lit(1.0)) \
        .withColumn("created_at", current_timestamp()) \
        .filter(col("competence_id").isNotNull()) \
        .dropDuplicates(["competence_id"]) \
        .select(
            "competence_id",
            "nom_competence",
            "categorie",
            "niveau_demande",
            "popularite_score",
            "created_at"
        )

    print("✅ Données Dim_Competence préparées")

    # ============================================
    # CHARGEMENT VERS BIGQUERY AVEC DÉDUPLICATION
    # ============================================

    bq_options = {
        "project": gcp_project_id,
        "dataset": bigquery_dataset,
        "temporaryGcsBucket": f"{gcp_project_id}-temp-spark-bq",
        "allowFieldAddition": "true",
        "allowSchemaEvolution": "true"
    }

    try:
        # ============================================
        # 1. FACT_OFFRESEMPLOI - Déduplication avant insertion
        # ============================================
        fact_table = f"{bigquery_dataset}.Fact_OffresEmploi"
        
        print(f"📊 Vérification des offres existantes dans {fact_table}...")
        
        try:
            # Lire les offre_id existants depuis BigQuery
            existing_offres = spark.read \
                .format("bigquery") \
                .option("table", fact_table) \
                .load() \
                .select("offre_id") \
                .distinct()
            
            existing_count = existing_offres.count()
            print(f"✅ {existing_count} offres existantes trouvées dans BigQuery")
            
            # Filtrer pour ne garder que les nouvelles offres (LEFT ANTI JOIN)
            new_offres = fact_offres_df.join(
                existing_offres,
                on="offre_id",
                how="left_anti"  # Garder uniquement ce qui n'existe pas dans existing_offres
            )
            
            new_count = new_offres.count()
            total_count = fact_offres_df.count()
            
            print(f"📈 {new_count} nouvelles offres à insérer (sur {total_count} au total)")
            
            if new_count > 0:
                # Insérer uniquement les nouvelles offres
                new_offres.write \
                    .format("bigquery") \
                    .option("table", fact_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                print(f"✅ Fact_OffresEmploi chargée ({new_count} nouvelles lignes)")
            else:
                print(f"ℹ️ Aucune nouvelle offre à insérer (toutes existent déjà)")
        
        except Exception as e:
            # Si la table n'existe pas encore, insérer toutes les offres
            if "Not found: Table" in str(e) or "404" in str(e):
                print(f"⚠️ Table {fact_table} n'existe pas encore, création...")
                fact_offres_df.write \
                    .format("bigquery") \
                    .option("table", fact_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                new_count = fact_offres_df.count()
                print(f"✅ Fact_OffresEmploi créée et chargée ({new_count} lignes)")
            else:
                raise

        # ============================================
        # 2. DIM_ENTREPRISE - Déduplication avant insertion
        # ============================================
        entreprise_table = f"{bigquery_dataset}.Dim_Entreprise"
        
        try:
            existing_entreprises = spark.read \
                .format("bigquery") \
                .option("table", entreprise_table) \
                .load() \
                .select("entreprise_id") \
                .distinct()
            
            new_entreprises = dim_entreprise_df.join(
                existing_entreprises,
                on="entreprise_id",
                how="left_anti"
            )
            
            new_entr_count = new_entreprises.count()
            
            if new_entr_count > 0:
                new_entreprises.write \
                    .format("bigquery") \
                    .option("table", entreprise_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                print(f"✅ Dim_Entreprise chargée ({new_entr_count} nouvelles lignes)")
            else:
                print(f"ℹ️ Aucune nouvelle entreprise à insérer")
        
        except Exception as e:
            if "Not found: Table" in str(e) or "404" in str(e):
                dim_entreprise_df.write \
                    .format("bigquery") \
                    .option("table", entreprise_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                new_entr_count = dim_entreprise_df.count()
                print(f"✅ Dim_Entreprise créée et chargée ({new_entr_count} lignes)")
            else:
                raise

        # ============================================
        # 3. DIM_LOCALISATION - Déduplication avant insertion
        # ============================================
        localisation_table = f"{bigquery_dataset}.Dim_Localisation"
        
        try:
            existing_localisations = spark.read \
                .format("bigquery") \
                .option("table", localisation_table) \
                .load() \
                .select("localisation_id") \
                .distinct()
            
            new_localisations = dim_localisation_df.join(
                existing_localisations,
                on="localisation_id",
                how="left_anti"
            )
            
            new_loc_count = new_localisations.count()
            
            if new_loc_count > 0:
                new_localisations.write \
                    .format("bigquery") \
                    .option("table", localisation_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                print(f"✅ Dim_Localisation chargée ({new_loc_count} nouvelles lignes)")
            else:
                print(f"ℹ️ Aucune nouvelle localisation à insérer")
        
        except Exception as e:
            if "Not found: Table" in str(e) or "404" in str(e):
                dim_localisation_df.write \
                    .format("bigquery") \
                    .option("table", localisation_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                new_loc_count = dim_localisation_df.count()
                print(f"✅ Dim_Localisation créée et chargée ({new_loc_count} lignes)")
            else:
                raise

        # ============================================
        # 4. DIM_COMPETENCE - Déduplication avant insertion
        # ============================================
        competence_table = f"{bigquery_dataset}.Dim_Competence"
        
        try:
            existing_competences = spark.read \
                .format("bigquery") \
                .option("table", competence_table) \
                .load() \
                .select("competence_id") \
                .distinct()
            
            new_competences = dim_competence_df.join(
                existing_competences,
                on="competence_id",
                how="left_anti"
            )
            
            new_comp_count = new_competences.count()
            
            if new_comp_count > 0:
                new_competences.write \
                    .format("bigquery") \
                    .option("table", competence_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                print(f"✅ Dim_Competence chargée ({new_comp_count} nouvelles lignes)")
            else:
                print(f"ℹ️ Aucune nouvelle compétence à insérer")
        
        except Exception as e:
            if "Not found: Table" in str(e) or "404" in str(e):
                dim_competence_df.write \
                    .format("bigquery") \
                    .option("table", competence_table) \
                    .option("writeMethod", "direct") \
                    .options(**bq_options) \
                    .mode("append") \
                    .save()
                
                new_comp_count = dim_competence_df.count()
                print(f"✅ Dim_Competence créée et chargée ({new_comp_count} lignes)")
            else:
                raise

        return {
            "fact_offres_count": new_count if 'new_count' in locals() else 0,
            "dim_entreprise_count": new_entr_count if 'new_entr_count' in locals() else 0,
            "dim_localisation_count": new_loc_count if 'new_loc_count' in locals() else 0,
            "dim_competence_count": new_comp_count if 'new_comp_count' in locals() else 0,
            "status": "SUCCESS"
        }

    except Exception as e:
        print(f"❌ Erreur lors du chargement BigQuery: {e}")
        return {
            "error": str(e),
            "status": "FAILED"
        }


def main():
    """Fonction principale"""
    print("🚀 Démarrage du chargement Spark Batch - BigQuery")

    # Configuration depuis variables d'environnement
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "noble-anvil-479619-h9")
    bigquery_dataset = os.getenv("BIGQUERY_DATASET", "jobmatching_dw")
    minio_bucket = os.getenv("MINIO_BUCKET", "processed-data")

    # Essayer d'abord jobs_enriched_sectors (avec secteurs), sinon jobs_parsed
    input_path = f"s3a://{minio_bucket}/jobs_enriched_sectors"

    print(f"📋 Configuration:")
    print(f"   GCP Project: {gcp_project_id}")
    print(f"   BigQuery Dataset: {bigquery_dataset}")
    print(f"   Input Path: {input_path} (avec fallback sur jobs_parsed)")

    # Variables pour le logging
    start_time = datetime.now()
    execution_id = os.getenv("AIRFLOW_RUN_ID", None)
    airflow_dag_id = os.getenv("AIRFLOW_DAG_ID", None)
    airflow_task_id = os.getenv("AIRFLOW_TASK_ID", None)
    statut = "SUCCESS"
    records_processed = 0
    error_message = None
    error_stack_trace = None

    try:
        # Créer la session Spark
        spark = create_spark_session()
        print("✅ Session Spark créée")

        # Charger les données
        result = process_bigquery_load(spark, input_path, bigquery_dataset, gcp_project_id)

        if result["status"] == "SUCCESS":
            statut = "SUCCESS"
            records_processed = result.get("fact_offres_count", 0)
            print("✅ Chargement BigQuery terminé avec succès")
            print("📊 Statistiques:")
            for key, value in result.items():
                if key != "status":
                    print(f"   {key}: {value}")
        else:
            statut = "FAILED"
            error_message = result.get("error", "Échec du chargement")
            print(f"❌ Échec du chargement: {error_message}")
            sys.exit(1)

    except Exception as e:
        statut = "FAILED"
        error_message = str(e)
        import traceback
        error_stack_trace = traceback.format_exc()
        print(f"❌ Erreur: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Écrire le log dans BigQuery
        end_time = datetime.now()
        try:
            if 'spark' in locals():
                write_processing_log(
                    spark=spark,
                    job_name="load_to_bigquery",
                    job_type="spark_batch",
                    start_time=start_time,
                    end_time=end_time,
                    statut=statut,
                    records_processed=records_processed,
                    records_success=records_processed if statut == "SUCCESS" else 0,
                    records_failed=0 if statut == "SUCCESS" else records_processed,
                    error_message=error_message,
                    error_stack_trace=error_stack_trace,
                    execution_id=execution_id,
                    airflow_dag_id=airflow_dag_id,
                    airflow_task_id=airflow_task_id
                )
        except Exception as log_error:
            print(f"⚠️  Erreur lors de l'écriture du log: {log_error}")
        
        if 'spark' in locals():
            spark.stop()
            print("✅ Session Spark arrêtée")


if __name__ == "__main__":
    main()
