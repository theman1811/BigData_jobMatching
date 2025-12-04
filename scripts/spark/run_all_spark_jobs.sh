#!/bin/bash
# ============================================
# Script de lancement - Tous les Jobs Spark
# ============================================
# Lance tous les jobs Spark dans l'ordre approprié

set -e  # Arrêter le script en cas d'erreur

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Lancement de tous les jobs Spark - Pipeline Complet"
echo "📁 Projet: $PROJECT_ROOT"
echo ""

# Fonction pour exécuter un job
run_job() {
    local job_name="$1"
    local script_path="$2"
    local description="$3"

    echo "🎯 $job_name: $description"
    echo "📄 Script: $script_path"

    if [ -f "$script_path" ]; then
        echo "▶️  Démarrage..."
        bash "$script_path"

        if [ $? -eq 0 ]; then
            echo "✅ $job_name terminé avec succès"
        else
            echo "❌ $job_name a échoué"
            exit 1
        fi
    else
        echo "❌ Script introuvable: $script_path"
        exit 1
    fi

    echo "⏱️  Pause de 10 secondes..."
    sleep 10
    echo ""
}

# ============================================
# JOBS SPARK STREAMING (à lancer en arrière-plan)
# ============================================

echo "🔄 JOBS STREAMING (à lancer manuellement en arrière-plan):"
echo "   1. Consommateur Kafka Jobs: scripts/spark/run_consume_jobs.sh"
echo "   2. Consommateur Kafka CVs: scripts/spark/run_consume_cvs.sh (À FAIRE)"
echo ""

# ============================================
# JOBS SPARK BATCH (séquentiels)
# ============================================

echo "🔧 JOBS BATCH (exécution séquentielle):"
echo ""

# 1. Parsing des offres HTML
run_job \
    "Parse Jobs HTML" \
    "$SCRIPT_DIR/run_parse_jobs.sh" \
    "Parser HTML → JSON structuré"

# 2. Extraction des compétences (si disponible)
if [ -f "$SCRIPT_DIR/run_extract_skills.sh" ]; then
    run_job \
        "Extract Skills" \
        "$SCRIPT_DIR/run_extract_skills.sh" \
        "Extraction NLP compétences"
fi

# 3. Extraction des salaires (si disponible)
if [ -f "$SCRIPT_DIR/run_extract_salary.sh" ]; then
    run_job \
        "Extract Salary" \
        "$SCRIPT_DIR/run_extract_salary.sh" \
        "Parsing salaires FCFA"
fi

# 4. Déduplication (si disponible)
if [ -f "$SCRIPT_DIR/run_deduplicate.sh" ]; then
    run_job \
        "Deduplicate" \
        "$SCRIPT_DIR/run_deduplicate.sh" \
        "Déduplication inter-sources"
fi

# 5. Matching (si disponible)
if [ -f "$SCRIPT_DIR/run_matching.sh" ]; then
    run_job \
        "Matching" \
        "$SCRIPT_DIR/run_matching.sh" \
        "Calcul matching offres-CVs"
fi

# 6. Chargement BigQuery (toujours en dernier)
run_job \
    "Load BigQuery" \
    "$SCRIPT_DIR/run_load_bigquery.sh" \
    "Chargement vers BigQuery"

echo "🎉 Tous les jobs Spark ont été exécutés avec succès!"
echo ""
echo "📋 Résumé du pipeline:"
echo "   ✅ Streaming: Jobs consommés depuis Kafka → MinIO"
echo "   ✅ Batch: HTML parsé → Données structurées → BigQuery"
echo ""
echo "🔄 Pour les jobs streaming, lancez manuellement:"
echo "   scripts/spark/run_consume_jobs.sh &"
echo ""
echo "📊 Prochaine étape: Configuration Airflow DAGs (Phase 5)"
