#!/bin/bash

# ============================================
# Spark Job - Extract Salary Runner
# ============================================
# Script pour lancer le job d'extraction et normalisation des salaires
#
# Usage: ./run_extract_salary.sh [options]
# Options:
#   --env-file FILE    : Fichier de configuration (défaut: config.env)
#   --master URL       : URL du Spark Master (défaut: spark://spark-master:7077)
#   --deploy-mode MODE : Mode de déploiement (client/cluster, défaut: client)
#   --dry-run          : Afficher la commande sans l'exécuter
#   --help             : Afficher l'aide

set -e  # Arrêter en cas d'erreur

# Configuration par défaut
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/config.env"
SPARK_MASTER="spark://spark-master:7077"
DEPLOY_MODE="client"
DRY_RUN=false

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction d'affichage des messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Fonction d'affichage de l'aide
show_help() {
    cat << EOF
Script de lancement du job Spark d'extraction de salaires

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --env-file FILE       Fichier de configuration (défaut: $ENV_FILE)
    --master URL          URL du Spark Master (défaut: $SPARK_MASTER)
    --deploy-mode MODE    Mode de déploiement: client ou cluster (défaut: $DEPLOY_MODE)
    --dry-run             Afficher la commande sans l'exécuter
    --help               Afficher cette aide

EXEMPLES:
    $0                                    # Lancement avec configuration par défaut
    $0 --dry-run                         # Aperçu de la commande
    $0 --env-file /path/to/config.env     # Configuration personnalisée
    $0 --master spark://localhost:7077   # Spark Master local

CONFIGURATION REQUISE:
Le fichier de configuration doit définir ces variables:
    MINIO_ENDPOINT=http://minio:9000
    MINIO_ACCESS_KEY=minioadmin
    MINIO_SECRET_KEY=minioadmin123

PARTICULARITÉS AFRIQUE:
- Le job ne bloque PAS si aucun salaire n'est trouvé
- Taux de détection peut être faible (< 50%)
- Traitement adapté au contexte ivoirien (FCFA)

EOF
}

# Parsing des arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --master)
            SPARK_MASTER="$2"
            shift 2
            ;;
        --deploy-mode)
            DEPLOY_MODE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Option inconnue: $1"
            log_error "Utilisez --help pour voir les options disponibles"
            exit 1
            ;;
    esac
done

# Vérification des prérequis
log_info "Vérification des prérequis..."

# Vérifier que le fichier de configuration existe
if [[ ! -f "$ENV_FILE" ]]; then
    log_error "Fichier de configuration introuvable: $ENV_FILE"
    log_error "Utilisez --env-file pour spécifier un autre fichier"
    exit 1
fi

# Charger la configuration
log_info "Chargement de la configuration depuis $ENV_FILE"
set -a
source "$ENV_FILE"
set +a

# Vérifier les variables essentielles
REQUIRED_VARS=("MINIO_ENDPOINT" "MINIO_ACCESS_KEY" "MINIO_SECRET_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        log_error "Variable requise non définie: $var"
        exit 1
    fi
done

# Vérifier que le job Spark existe
JOB_FILE="$PROJECT_ROOT/spark/batch/extract_salary.py"
if [[ ! -f "$JOB_FILE" ]]; then
    log_error "Job Spark introuvable: $JOB_FILE"
    exit 1
fi

# Construction de la commande Docker
SPARK_SUBMIT_CMD="docker exec bigdata_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --packages org.apache.hadoop:hadoop-aws:3.3.4 \
    --name SalaryExtractor \
    --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
    --conf spark.hadoop.fs.s3a.access.key=minioadmin \
    --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
    --conf spark.sql.adaptive.enabled=true \
    --conf spark.sql.adaptive.coalescePartitions.enabled=true \
    --conf spark.driver.memory=2g \
    --conf spark.executor.memory=4g \
    --conf spark.executor.cores=2 \
    --conf spark.sql.shuffle.partitions=200 \
    /opt/spark-apps/batch/extract_salary.py"

# Afficher la configuration
log_info "Configuration du job:"
echo "  Spark Master: $SPARK_MASTER"
echo "  Deploy Mode: $DEPLOY_MODE"
echo "  Job File: $JOB_FILE"
echo "  Env File: $ENV_FILE"
echo "  MinIO Endpoint: $MINIO_ENDPOINT"

# Afficher la commande complète
log_info "Commande Docker:"
echo "  $SPARK_SUBMIT_CMD"

if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "Mode dry-run: commande affichée mais non exécutée"
    exit 0
fi

# Exécution du job
log_info "Lancement du job d'extraction de salaires..."
log_warning "Note: En Afrique, les salaires sont souvent non spécifiés - traitement non-bloquant"

# Exécuter la commande
START_TIME=$(date +%s)
if eval "$SPARK_SUBMIT_CMD"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_success "Job d'extraction de salaires terminé avec succès"
    log_success "Durée d'exécution: ${DURATION}s"

    # Suggestions pour la suite
    log_info "Prochaines étapes suggérées:"
    echo "  1. Vérifier les salaires extraits dans MinIO"
    echo "  2. Lancer la déduplication: ./run_deduplicate.sh"
    echo "  3. Charger vers BigQuery: ./run_load_bigquery.sh"
    echo "  4. Noter que le taux de détection peut être < 50% en Afrique"

else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_error "Échec du job d'extraction de salaires après ${DURATION}s"
    log_error "Consultez les logs Spark pour diagnostiquer l'erreur"
    log_warning "Rappel: Le job est conçu pour ne pas bloquer si aucun salaire n'est trouvé"
    exit 1
fi
