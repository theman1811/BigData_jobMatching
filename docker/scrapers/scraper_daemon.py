#!/usr/bin/env python3
"""
============================================
Scraper Daemon - Web Scraping Service
============================================
Ce service écoute les commandes Kafka et lance les scrapers appropriés
"""

import os
import time
import json
import logging
from typing import Dict, Any
from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
KAFKA_TOPIC_COMMANDS = 'scraper-commands'
KAFKA_TOPIC_STATUS = 'scraper-status'

class ScraperDaemon:
    """Service daemon pour gérer les scrapers"""
    
    def __init__(self):
        self.running = True
        self.setup_logging()
        self.setup_kafka()
        
    def setup_logging(self):
        """Configure le logging"""
        logger.add(
            "/app/logs/scraper_daemon.log",
            rotation="1 day",
            retention="7 days",
            level="INFO"
        )
        logger.info("🚀 Scraper Daemon démarré")
    
    def setup_kafka(self):
        """Configure les connexions Kafka"""
        try:
            self.consumer = KafkaConsumer(
                KAFKA_TOPIC_COMMANDS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='scraper-daemon-group'
            )
            
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            logger.info(f"✅ Connecté à Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion Kafka: {e}")
            raise
    
    def send_status(self, status: str, message: str, data: Dict[str, Any] = None):
        """Envoie un statut au topic Kafka"""
        status_msg = {
            'timestamp': time.time(),
            'status': status,
            'message': message,
            'data': data or {}
        }
        self.producer.send(KAFKA_TOPIC_STATUS, status_msg)
        logger.info(f"📤 Statut envoyé: {status} - {message}")
    
    def execute_scraping_command(self, command: Dict[str, Any]):
        """Exécute une commande de scraping"""
        try:
            scraper_type = command.get('scraper_type')
            params = command.get('params', {})
            
            logger.info(f"🔍 Exécution scraper: {scraper_type}")
            logger.info(f"   Paramètres: {params}")
            
            # TODO: Implémenter les scrapers spécifiques
            # Pour l'instant, juste un placeholder
            self.send_status(
                'running',
                f'Scraper {scraper_type} démarré',
                {'scraper': scraper_type, 'params': params}
            )
            
            # Simulation
            time.sleep(2)
            
            self.send_status(
                'completed',
                f'Scraper {scraper_type} terminé',
                {'scraper': scraper_type, 'items_scraped': 0}
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution scraper: {e}")
            self.send_status(
                'error',
                f'Erreur scraper: {str(e)}',
                {'error': str(e)}
            )
    
    def run(self):
        """Boucle principale du daemon"""
        logger.info("👂 En écoute des commandes de scraping...")
        
        try:
            while self.running:
                # Poll pour les nouveaux messages
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        logger.info(f"📨 Commande reçue: {record.value}")
                        self.execute_scraping_command(record.value)
                
                # Heartbeat
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt du daemon demandé")
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Nettoyage avant arrêt"""
        logger.info("🧹 Nettoyage...")
        self.consumer.close()
        self.producer.close()
        logger.info("👋 Daemon arrêté")

if __name__ == '__main__':
    daemon = ScraperDaemon()
    daemon.run()

