#!/usr/bin/env python3
"""
==========================================
Spark Batch - Logging Utilities
==========================================
Utilitaires pour écrire les logs d'exécution dans BigQuery Logs_Processing.
"""

import os
import uuid
import traceback
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit, col
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType, TimestampType
)


def create_logs_schema():
    """Crée le schéma pour la table Logs_Processing"""
    return StructType([
        StructField("log_id", StringType(), False),
        StructField("job_name", StringType(), True),
        StructField("job_type", StringType(), True),
        StructField("execution_id", StringType(), True),
        StructField("start_time", TimestampType(), True),
        StructField("end_time", TimestampType(), True),
        StructField("duration_seconds", IntegerType(), True),
        StructField("statut", StringType(), True),
        StructField("records_processed", IntegerType(), True),
        StructField("records_success", IntegerType(), True),
        StructField("records_failed", IntegerType(), True),
        StructField("error_message", StringType(), True),
        StructField("error_stack_trace", StringType(), True),
        StructField("environment", StringType(), True),
        StructField("spark_app_id", StringType(), True),
        StructField("airflow_dag_id", StringType(), True),
        StructField("airflow_task_id", StringType(), True),
        StructField("memory_used_mb", FloatType(), True),
        StructField("cpu_time_seconds", FloatType(), True),
    ])


def write_processing_log(
    spark: SparkSession,
    job_name: str,
    job_type: str,
    start_time: datetime,
    end_time: datetime,
    statut: str,
    records_processed: int = 0,
    records_success: int = 0,
    records_failed: int = 0,
    error_message: str = None,
    error_stack_trace: str = None,
    execution_id: str = None,
    airflow_dag_id: str = None,
    airflow_task_id: str = None,
    memory_used_mb: float = None,
    cpu_time_seconds: float = None
):
    """
    Écrit un log d'exécution dans la table Logs_Processing de BigQuery.
    
    Args:
        spark: Session Spark
        job_name: Nom du job (ex: "parse_jobs", "extract_skills")
        job_type: Type de job (ex: "spark_batch", "spark_streaming")
        start_time: Heure de début d'exécution
        end_time: Heure de fin d'exécution
        statut: Statut de l'exécution ("SUCCESS", "FAILED", "PARTIAL")
        records_processed: Nombre total de records traités
        records_success: Nombre de records traités avec succès
        records_failed: Nombre de records en échec
        error_message: Message d'erreur (si échec)
        error_stack_trace: Stack trace de l'erreur (si échec)
        execution_id: ID d'exécution unique (généré si None)
        airflow_dag_id: ID du DAG Airflow (si exécuté depuis Airflow)
        airflow_task_id: ID de la tâche Airflow (si exécuté depuis Airflow)
        memory_used_mb: Mémoire utilisée en MB (optionnel)
        cpu_time_seconds: Temps CPU utilisé en secondes (optionnel)
    """
    try:
        # Configuration BigQuery
        gcp_project_id = os.getenv("GCP_PROJECT_ID", "noble-anvil-479619-h9")
        bigquery_dataset = os.getenv("BIGQUERY_DATASET", "jobmatching_dw")
        # Format complet: project.dataset.table
        logs_table = f"{gcp_project_id}.{bigquery_dataset}.Logs_Processing"
        
        print(f"🔍 DEBUG Logging - Configuration BigQuery:")
        print(f"   GCP_PROJECT_ID env: {os.getenv('GCP_PROJECT_ID')}")
        print(f"   Project utilisé: {gcp_project_id}")
        print(f"   Dataset: {bigquery_dataset}")
        print(f"   Table complète: {logs_table}")
        
        # Générer un ID unique si non fourni
        if not execution_id:
            execution_id = str(uuid.uuid4())
        
        # Calculer la durée
        duration_seconds = int((end_time - start_time).total_seconds())
        
        # Récupérer l'ID de l'application Spark
        spark_app_id = spark.sparkContext.applicationId if spark.sparkContext else None
        
        # Récupérer l'environnement
        environment = os.getenv("ENVIRONMENT", "development")
        
        # Créer le DataFrame avec les données du log
        log_data = [{
            "log_id": str(uuid.uuid4()),
            "job_name": job_name,
            "job_type": job_type,
            "execution_id": execution_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "statut": statut,
            "records_processed": records_processed,
            "records_success": records_success,
            "records_failed": records_failed,
            "error_message": error_message[:500] if error_message else None,  # Limiter à 500 caractères
            "error_stack_trace": error_stack_trace[:2000] if error_stack_trace else None,  # Limiter à 2000 caractères
            "environment": environment,
            "spark_app_id": spark_app_id,
            "airflow_dag_id": airflow_dag_id,
            "airflow_task_id": airflow_task_id,
            "memory_used_mb": memory_used_mb,
            "cpu_time_seconds": cpu_time_seconds,
        }]
        
        # Créer le DataFrame
        log_df = spark.createDataFrame([log_data[0]], schema=create_logs_schema())
        
        # Déterminer le chemin des credentials selon le contexte
        creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_file:
            # Essayer le chemin Airflow puis Spark
            if os.path.exists("/opt/airflow/credentials/bq-service-account.json"):
                creds_file = "/opt/airflow/credentials/bq-service-account.json"
            elif os.path.exists("/opt/spark/credentials/bq-service-account.json"):
                creds_file = "/opt/spark/credentials/bq-service-account.json"
        
        print(f"   Credentials file: {creds_file}")
        print(f"   Credentials exists: {os.path.exists(creds_file) if creds_file else False}")
        
        # Options BigQuery - utiliser le format complet pour la table (project.dataset.table)
        # donc on ne passe PAS dataset dans les options pour éviter les conflits
        bq_options = {
            "table": logs_table,
            "writeMethod": "direct",
            "project": gcp_project_id,
            "parentProject": gcp_project_id,
            "temporaryGcsBucket": f"{gcp_project_id}-temp-spark-bq",
            "allowFieldAddition": "true",
            "allowSchemaEvolution": "true"
        }
        
        # Ajouter le fichier de credentials si disponible
        if creds_file and os.path.exists(creds_file):
            bq_options["credentialsFile"] = creds_file
            print(f"   ✅ Credentials ajoutés aux options")
        else:
            print(f"   ⚠️  Pas de credentials file trouvé")
        
        print(f"   BigQuery options: {bq_options}")
        
        # Écrire dans BigQuery
        log_df.write \
            .format("bigquery") \
            .options(**bq_options) \
            .mode("append") \
            .save()
        
        print(f"✅ Log écrit dans {logs_table}")
        print(f"   Job: {job_name}, Statut: {statut}, Durée: {duration_seconds}s, Records: {records_processed}")
        print(f"   Project: {gcp_project_id}, Dataset: {bigquery_dataset}")
        print(f"   Start time: {start_time}, End time: {end_time}")
        print(f"   Execution ID: {execution_id}")
        
    except Exception as e:
        # Ne pas faire échouer le job principal si l'écriture du log échoue
        print(f"⚠️  Erreur lors de l'écriture du log dans BigQuery: {e}")
        print(f"   Le job continue malgré cette erreur de logging")


def log_job_execution(
    spark: SparkSession,
    job_name: str,
    job_type: str = "spark_batch",
    execution_id: str = None,
    airflow_dag_id: str = None,
    airflow_task_id: str = None
):
    """
    Décorateur/Context manager pour logger automatiquement l'exécution d'un job.
    
    Usage:
        @log_job_execution(spark, "parse_jobs", "spark_batch")
        def my_job():
            # code du job
            return {"records_processed": 100, "status": "SUCCESS"}
    """
    class JobLogger:
        def __init__(self, func):
            self.func = func
            self.start_time = None
            self.spark = spark
            self.job_name = job_name
            self.job_type = job_type
            self.execution_id = execution_id or str(uuid.uuid4())
            self.airflow_dag_id = airflow_dag_id
            self.airflow_task_id = airflow_task_id
        
        def __call__(self, *args, **kwargs):
            self.start_time = datetime.now()
            records_processed = 0
            records_success = 0
            records_failed = 0
            statut = "SUCCESS"
            error_message = None
            error_stack_trace = None
            
            try:
                # Exécuter la fonction
                result = self.func(*args, **kwargs)
                
                # Extraire les métriques du résultat
                if isinstance(result, dict):
                    records_processed = result.get("records_processed", 0)
                    records_success = result.get("records_success", records_processed)
                    records_failed = result.get("records_failed", 0)
                    statut = result.get("status", "SUCCESS")
                    error_message = result.get("error", None)
                
                return result
                
            except Exception as e:
                statut = "FAILED"
                error_message = str(e)
                error_stack_trace = traceback.format_exc()
                raise
            
            finally:
                # Écrire le log
                end_time = datetime.now()
                write_processing_log(
                    spark=self.spark,
                    job_name=self.job_name,
                    job_type=self.job_type,
                    start_time=self.start_time,
                    end_time=end_time,
                    statut=statut,
                    records_processed=records_processed,
                    records_success=records_success,
                    records_failed=records_failed,
                    error_message=error_message,
                    error_stack_trace=error_stack_trace,
                    execution_id=self.execution_id,
                    airflow_dag_id=self.airflow_dag_id,
                    airflow_task_id=self.airflow_task_id
                )
    
    return JobLogger
