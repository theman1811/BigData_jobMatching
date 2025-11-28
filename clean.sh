#!/bin/bash

# ============================================
# Script de nettoyage - BigData Platform
# ============================================

echo "🧹 Nettoyage complet de la plateforme..."
echo ""
echo "⚠️  ATTENTION: Cette action va supprimer TOUTES les données!"
echo ""
read -p "Êtes-vous sûr? (oui/non): " confirm

if [ "$confirm" != "oui" ]; then
    echo "❌ Annulé."
    exit 0
fi

echo ""
echo "🛑 Arrêt des conteneurs..."
docker-compose down -v

echo ""
echo "🗑️  Suppression des volumes Docker..."
docker volume prune -f

echo ""
echo "🧹 Nettoyage des fichiers locaux..."
rm -rf ./airflow/logs/*
rm -rf ./data/raw/*
rm -rf ./data/processed/*

echo ""
echo "✅ Nettoyage terminé!"
echo ""
echo "📝 Pour redémarrer la plateforme:"
echo "   ./start.sh"
echo ""

