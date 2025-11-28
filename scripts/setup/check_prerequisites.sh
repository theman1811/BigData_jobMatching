#!/bin/bash

# ============================================
# Script de vérification des prérequis
# ============================================

echo "🔍 Vérification des prérequis..."
echo ""

errors=0

# Vérifier Docker
echo -n "✓ Docker: "
if command -v docker &> /dev/null; then
    docker_version=$(docker --version | cut -d ' ' -f3 | cut -d ',' -f1)
    echo "✅ installé (version $docker_version)"
else
    echo "❌ non installé"
    errors=$((errors + 1))
fi

# Vérifier Docker Compose
echo -n "✓ Docker Compose: "
if command -v docker-compose &> /dev/null; then
    compose_version=$(docker-compose --version | cut -d ' ' -f4 | cut -d ',' -f1)
    echo "✅ installé (version $compose_version)"
else
    echo "❌ non installé"
    errors=$((errors + 1))
fi

# Vérifier que Docker est lancé
echo -n "✓ Docker daemon: "
if docker info > /dev/null 2>&1; then
    echo "✅ en cours d'exécution"
else
    echo "❌ non démarré"
    errors=$((errors + 1))
fi

# Vérifier Python
echo -n "✓ Python: "
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version | cut -d ' ' -f2)
    echo "✅ installé (version $python_version)"
else
    echo "⚠️  non installé (optionnel pour développement local)"
fi

# Vérifier la mémoire disponible
echo -n "✓ Mémoire RAM: "
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    total_mem=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    echo "$total_mem GB"
    if [ $total_mem -lt 8 ]; then
        echo "   ⚠️  Recommandé: 8 GB minimum (16 GB idéal)"
    else
        echo "   ✅ Suffisant"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    total_mem=$(free -g | awk '/^Mem:/{print $2}')
    echo "$total_mem GB"
    if [ $total_mem -lt 8 ]; then
        echo "   ⚠️  Recommandé: 8 GB minimum (16 GB idéal)"
    else
        echo "   ✅ Suffisant"
    fi
fi

# Vérifier l'espace disque
echo -n "✓ Espace disque disponible: "
if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
    disk_space=$(df -h . | awk 'NR==2 {print $4}')
    echo "$disk_space"
    echo "   ℹ️  Recommandé: 10 GB minimum"
fi

echo ""
if [ $errors -eq 0 ]; then
    echo "✅ Tous les prérequis sont satisfaits!"
    echo ""
    echo "📝 Prochaine étape:"
    echo "   ./start.sh"
else
    echo "❌ Certains prérequis sont manquants."
    echo ""
    echo "📝 Installation:"
    echo "   • Docker Desktop: https://www.docker.com/products/docker-desktop"
fi

echo ""

