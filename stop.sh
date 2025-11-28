#!/bin/bash

# ============================================
# Script d'arrêt - BigData Platform
# ============================================

echo "🛑 Arrêt de la plateforme Big Data..."
echo ""

docker-compose down

echo ""
echo "✅ Plateforme arrêtée!"
echo ""
echo "📝 Pour supprimer aussi les volumes (données):"
echo "   docker-compose down -v"
echo ""

