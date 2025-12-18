from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0
}

dag = DAG(
    'platform_monitoring',
    default_args=default_args,
    description='Surveillance légère du pipeline (Kafka, MinIO, Spark)',
    schedule_interval='*/30 * * * *',  # Toutes les 30 minutes
    catchup=False,
    tags=['monitoring']
)


def check_kafka_lag(**context):
    """Vérifie le consumer lag réel pour tous les consumer groups Kafka."""
    try:
        from kafka import KafkaAdminClient, KafkaConsumer
        from kafka.structs import TopicPartition
        from kafka.errors import KafkaError
        
        # Configuration Kafka depuis les variables d'environnement
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        # Dans Docker, utiliser le nom du service, sinon utiliser localhost
        if "kafka:" in bootstrap_servers:
            # Déjà configuré pour Docker
            kafka_servers = bootstrap_servers
        else:
            # Depuis l'extérieur du réseau Docker
            kafka_servers = bootstrap_servers.replace("localhost", "kafka").replace(":9092", ":29092")
        
        print(f"🔌 Connexion à Kafka: {kafka_servers}")
        
        # Créer le client Admin
        admin_client = KafkaAdminClient(
            bootstrap_servers=kafka_servers.split(","),
            client_id='airflow-monitoring',
            request_timeout_ms=10000
        )
        
        # Créer un consumer pour obtenir les offsets de fin
        offset_consumer = KafkaConsumer(
            bootstrap_servers=kafka_servers.split(","),
            consumer_timeout_ms=5000
        )
        
        try:
            # Lister tous les consumer groups
            groups_response = admin_client.list_consumer_groups()
            # list_consumer_groups() retourne une liste de tuples (group_id, group_type)
            consumer_groups = [group[0] for group in groups_response if isinstance(group, tuple)]
            
            if not consumer_groups:
                print("ℹ️  Aucun consumer group actif trouvé")
                admin_client.close()
                offset_consumer.close()
                return
            
            print(f"📋 {len(consumer_groups)} consumer group(s) trouvé(s):")
            
            total_lag = 0
            groups_with_lag = []
            
            # Vérifier le lag pour chaque consumer group
            for group_id in consumer_groups:
                try:
                    # Obtenir les offsets commités pour ce consumer group
                    committed_offsets = admin_client.list_consumer_group_offsets(group_id)
                    
                    if not committed_offsets:
                        print(f"   ⚠️  {group_id}: Aucun offset commité (groupe inactif ou vide)")
                        continue
                    
                    group_lag = 0
                    group_info = {
                        'group_id': group_id,
                        'partitions': [],
                        'total_lag': 0
                    }
                    
                    # Pour chaque topic/partition avec un offset commité
                    for tp, offset_metadata in committed_offsets.items():
                        try:
                            # Créer un TopicPartition pour obtenir l'offset de fin
                            topic_partition = TopicPartition(tp.topic, tp.partition)
                            
                            # Obtenir l'offset de fin (dernière position disponible)
                            end_offsets = offset_consumer.end_offsets([topic_partition])
                            end_offset = end_offsets[topic_partition] if topic_partition in end_offsets else 0
                            
                            # L'offset commité est dans offset_metadata.offset
                            # OffsetAndMetadata a un attribut 'offset'
                            committed_offset = offset_metadata.offset
                            
                            # Calculer le lag
                            lag = max(0, end_offset - committed_offset)
                            group_lag += lag
                            
                            group_info['partitions'].append({
                                'topic': tp.topic,
                                'partition': tp.partition,
                                'committed': committed_offset,
                                'end': end_offset,
                                'lag': lag
                            })
                        except Exception as part_error:
                            print(f"      ⚠️  Erreur pour {tp.topic}[{tp.partition}]: {part_error}")
                            continue
                    
                    group_info['total_lag'] = group_lag
                    total_lag += group_lag
                    
                    if group_lag > 0:
                        groups_with_lag.append(group_info)
                        print(f"   ⚠️  {group_id}: Lag total = {group_lag:,} messages")
                        for part_info in group_info['partitions']:
                            if part_info['lag'] > 0:
                                print(f"      └─ {part_info['topic']}[{part_info['partition']}]: "
                                      f"lag={part_info['lag']:,} "
                                      f"(committed={part_info['committed']:,}, end={part_info['end']:,})")
                    else:
                        if group_info['partitions']:
                            print(f"   ✅ {group_id}: Aucun lag ({len(group_info['partitions'])} partition(s))")
                            # Afficher un résumé des partitions
                            topics = {}
                            for part_info in group_info['partitions']:
                                topic = part_info['topic']
                                if topic not in topics:
                                    topics[topic] = []
                                topics[topic].append(part_info['partition'])
                            
                            for topic, partitions in topics.items():
                                print(f"      └─ {topic}: {len(partitions)} partition(s) à jour")
                        else:
                            print(f"   ✅ {group_id}: Aucun lag")
                        
                except Exception as e:
                    print(f"   ❌ {group_id}: Erreur lors de la vérification - {str(e)}")
                    import traceback
                    print(f"      Détails: {traceback.format_exc()}")
                    continue
            
            # Résumé global
            print(f"\n📊 Résumé:")
            print(f"   Consumer groups actifs: {len(consumer_groups)}")
            print(f"   Groups avec lag: {len(groups_with_lag)}")
            print(f"   Lag total: {total_lag:,} messages")
            
            # Alerte si lag élevé
            if total_lag > 10000:
                print(f"   🚨 ALERTE: Lag élevé détecté ({total_lag:,} messages)")
            elif total_lag > 1000:
                print(f"   ⚠️  ATTENTION: Lag modéré détecté ({total_lag:,} messages)")
            elif total_lag == 0:
                print(f"   ✅ Tous les consumers sont à jour")
            
            admin_client.close()
            offset_consumer.close()
            
        except Exception as e:
            print(f"❌ Erreur lors de la liste des consumer groups: {e}")
            import traceback
            print(traceback.format_exc())
            admin_client.close()
            offset_consumer.close()
            
    except ImportError:
        print("⚠️  Bibliothèque 'kafka-python' non disponible.")
        print("   Installation requise: pip install kafka-python")
        print("   Ou ajouter 'kafka-python==2.0.2' au Dockerfile Airflow")
    except Exception as e:
        print(f"❌ Erreur lors de la vérification Kafka: {e}")
        import traceback
        print(traceback.format_exc())


def check_minio_space(**context):
    """Vérifie l'espace utilisé dans MinIO via l'API."""
    try:
        from minio import Minio
        from urllib.parse import urlparse
        
        # Configuration MinIO depuis les variables d'environnement
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        access_key = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
        
        # Parser l'URL pour extraire host et port
        parsed = urlparse(minio_endpoint)
        host = parsed.hostname or "minio"
        port = parsed.port or 9000
        secure = parsed.scheme == "https"
        
        # Créer le client MinIO
        client = Minio(
            f"{host}:{port}",
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # Lister tous les buckets et calculer la taille totale
        total_size = 0
        bucket_count = 0
        object_count = 0
        
        buckets = client.list_buckets()
        for bucket in buckets:
            bucket_count += 1
            print(f"📦 Bucket: {bucket.name}")
            
            # Lister tous les objets dans le bucket
            objects = client.list_objects(bucket.name, recursive=True)
            bucket_size = 0
            bucket_objects = 0
            
            for obj in objects:
                bucket_size += obj.size
                bucket_objects += 1
            
            total_size += bucket_size
            object_count += bucket_objects
            
            if bucket_size > 0:
                print(f"   └─ {bucket_objects} objets, {bucket_size / 1e9:.2f} GB")
        
        # Afficher le résumé
        print(f"\n✅ MinIO: {bucket_count} buckets, {object_count} objets")
        print(f"💾 Espace total utilisé: {total_size / 1e9:.2f} GB")
        
        # Note: MinIO ne fournit pas directement l'espace total disponible via l'API
        # Pour obtenir cette info, il faudrait accéder au système de fichiers du conteneur MinIO
        print("ℹ️  Pour connaître l'espace disque total, vérifier le volume Docker 'minio_data'")
        
    except ImportError:
        print("⚠️  Bibliothèque 'minio' non disponible. Installation requise dans l'image Airflow.")
    except Exception as e:
        print(f"❌ Erreur lors de la vérification MinIO: {e}")


def _try_spark_json_endpoint(spark_ui_url):
    """Essaie d'obtenir les informations du cluster via l'endpoint /json."""
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
    import json
    
    try:
        json_url = f"{spark_ui_url}/json"
        print(f"   Tentative avec: {json_url}")
        alt_req = Request(json_url)
        alt_req.add_header('Accept', 'application/json')
        
        with urlopen(alt_req, timeout=5) as alt_response:
            content_type = alt_response.headers.get('Content-Type', '')
            alt_data = alt_response.read().decode('utf-8')
            
            if not alt_data.strip():
                print(f"   Réponse vide de l'endpoint /json")
                return False
            
            # Vérifier si c'est du HTML
            if alt_data.strip().startswith('<') or 'text/html' in content_type:
                print(f"   L'endpoint /json retourne aussi du HTML (type: {content_type})")
                print(f"   Premiers caractères: {alt_data[:200]}")
                return False
            
            try:
                cluster_info = json.loads(alt_data)
            except json.JSONDecodeError as json_err:
                print(f"   Erreur de parsing JSON de /json: {json_err}")
                print(f"   Réponse reçue: {alt_data[:500]}")
                return False
            
            print(f"✅ Informations du cluster récupérées via /json")
            
            # Afficher les informations du cluster
            workers = cluster_info.get('workers', [])
            if workers:
                alive_workers = [w for w in workers if w.get('state') == 'ALIVE']
                print(f"   Workers actifs: {len(alive_workers)}/{len(workers)}")
                for worker in alive_workers:
                    print(f"      └─ {worker.get('id', 'N/A')}: {worker.get('host', 'N/A')} "
                          f"(cores: {worker.get('cores', 0)}, mémoire: {worker.get('memory', 0)})")
            else:
                print(f"   Aucun worker trouvé dans la réponse")
            
            # Les applications peuvent être dans différents champs selon la version de Spark
            apps = cluster_info.get('activeapps', [])
            if not apps:
                apps = cluster_info.get('applications', [])
            if not apps:
                apps = cluster_info.get('activeApplications', [])
            
            if apps:
                print(f"   Applications actives: {len(apps)}")
                for app in apps:
                    app_name = app.get('name', app.get('appName', 'N/A'))
                    app_id = app.get('id', app.get('appId', 'N/A'))
                    app_state = app.get('state', app.get('status', 'N/A'))
                    cores = app.get('cores', app.get('coresUsed', 'N/A'))
                    memory = app.get('memory', app.get('memoryUsed', 'N/A'))
                    print(f"      └─ {app_name} (id: {app_id}, état: {app_state})")
                    if cores != 'N/A' or memory != 'N/A':
                        print(f"         └─ Ressources: cores={cores}, mémoire={memory}")
            else:
                print(f"   Aucune application active trouvée")
            
            return True
            
    except HTTPError as http_err:
        print(f"   Erreur HTTP avec /json: {http_err.code} - {http_err.reason}")
        return False
    except URLError as url_err:
        print(f"   Erreur de connexion avec /json: {url_err.reason}")
        return False
    except Exception as alt_error:
        print(f"   Erreur avec l'endpoint /json: {alt_error}")
        import traceback
        print(f"   Détails: {traceback.format_exc()}")
        return False


def check_spark_jobs(**context):
    """Vérifie les applications Spark actives via l'API REST du Spark Master."""
    try:
        import json
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError
        from datetime import datetime, timedelta
        
        # Extraire l'hostname du Spark Master depuis l'URL
        spark_master_url = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
        
        # Parser l'URL pour extraire le hostname
        # Format: spark://hostname:port
        if spark_master_url.startswith("spark://"):
            hostname = spark_master_url.replace("spark://", "").split(":")[0]
        else:
            hostname = "spark-master"
        
        # L'API REST du Spark Master est sur le port 8080 (Web UI)
        spark_ui_url = f"http://{hostname}:8080"
        api_url = f"{spark_ui_url}/api/v1/applications"
        
        print(f"🔌 Connexion au Spark Master: {spark_master_url}")
        print(f"🌐 Spark UI: {spark_ui_url}")
        print(f"🌐 API REST: {api_url}")
        
        # Vérifier d'abord si le Spark UI est accessible
        try:
            ui_check = Request(spark_ui_url)
            with urlopen(ui_check, timeout=5) as ui_response:
                ui_status = ui_response.getcode()
                print(f"✅ Spark UI accessible (code HTTP: {ui_status})")
        except Exception as ui_error:
            print(f"⚠️  Impossible d'accéder au Spark UI: {ui_error}")
            print(f"   Vérifiez que le Spark Master est démarré et accessible")
            return
        
        try:
            # Faire la requête à l'API REST
            req = Request(api_url)
            req.add_header('Accept', 'application/json')
            
            with urlopen(req, timeout=10) as response:
                # Vérifier le type de contenu
                content_type = response.headers.get('Content-Type', '')
                response_data = response.read().decode('utf-8')
                
                # Vérifier si c'est bien du JSON
                if 'application/json' not in content_type and response_data.strip():
                    print(f"⚠️  Attention: Le serveur a retourné '{content_type}' au lieu de JSON")
                    print(f"   Premiers caractères de la réponse: {response_data[:200]}")
                    
                    # Si c'est du HTML, peut-être que l'API n'est pas disponible
                    if response_data.strip().startswith('<'):
                        print(f"   La réponse semble être du HTML. L'endpoint /api/v1/applications n'est pas disponible sur le Spark Master.")
                        print(f"   Le Spark Master Web UI ne fournit pas directement l'API REST des applications.")
                        print(f"   Tentative avec l'endpoint alternatif /json pour obtenir les infos du cluster...")
                        if _try_spark_json_endpoint(spark_ui_url):
                            return
                        print(f"\n💡 Note: Pour obtenir les détails des applications Spark individuelles,")
                        print(f"   accédez à l'UI de chaque application (généralement sur le port 4040)")
                        print(f"   ou utilisez l'API REST Spark sur le port 6066 si configuré.")
                        print(f"   Spark Master UI: {spark_ui_url}")
                        return
                
                # Essayer de parser le JSON
                if not response_data.strip():
                    print("ℹ️  Aucune donnée retournée par l'API (réponse vide)")
                    print(f"   Tentative avec l'endpoint alternatif /json...")
                    if _try_spark_json_endpoint(spark_ui_url):
                        return
                    print(f"   Aucune information disponible via les endpoints standards")
                    return
                    
                try:
                    data = json.loads(response_data)
                except json.JSONDecodeError as json_err:
                    print(f"❌ Impossible de parser la réponse comme JSON: {json_err}")
                    print(f"   Réponse reçue (premiers 500 caractères): {response_data[:500]}")
                    print(f"   Tentative avec l'endpoint alternatif /json...")
                    if _try_spark_json_endpoint(spark_ui_url):
                        return
                    print(f"   Aucune information disponible via les endpoints standards")
                    return
                
                if not data:
                    print("ℹ️  Aucune application Spark active")
                    return
                
                print(f"\n📊 {len(data)} application(s) Spark active(s):\n")
                
                total_executors = 0
                total_cores = 0
                total_memory = 0
                
                for app in data:
                    app_id = app.get('id', 'N/A')
                    app_name = app.get('name', 'N/A')
                    attempts = app.get('attempts', [])
                    
                    if not attempts:
                        print(f"   ⚠️  {app_name} ({app_id}): Aucune tentative trouvée")
                        continue
                    
                    # Prendre la dernière tentative (la plus récente)
                    latest_attempt = attempts[-1]
                    start_time = latest_attempt.get('startTime', 'N/A')
                    end_time = latest_attempt.get('endTime')
                    duration = latest_attempt.get('duration', 0)
                    spark_user = latest_attempt.get('sparkUser', 'N/A')
                    completed = latest_attempt.get('completed', False)
                    
                    # Calculer la durée si l'application est toujours en cours
                    if not end_time and start_time != 'N/A':
                        try:
                            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            now_dt = datetime.now(start_dt.tzinfo)
                            duration_seconds = int((now_dt - start_dt).total_seconds())
                            duration_str = f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m {duration_seconds % 60}s"
                        except:
                            duration_str = f"{duration}ms"
                    elif duration > 0:
                        duration_ms = duration
                        duration_seconds = duration_ms // 1000
                        duration_str = f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m {duration_seconds % 60}s"
                    else:
                        duration_str = "N/A"
                    
                    status_icon = "✅" if completed else "🔄"
                    status_text = "Terminée" if completed else "En cours"
                    
                    print(f"   {status_icon} {app_name} ({app_id})")
                    print(f"      └─ Statut: {status_text}")
                    print(f"      └─ Utilisateur: {spark_user}")
                    print(f"      └─ Début: {start_time}")
                    if end_time:
                        print(f"      └─ Fin: {end_time}")
                    print(f"      └─ Durée: {duration_str}")
                    
                    # Essayer d'obtenir plus de détails depuis l'endpoint de l'application
                    try:
                        app_detail_url = f"{spark_ui_url}/api/v1/applications/{app_id}"
                        detail_req = Request(app_detail_url)
                        detail_req.add_header('Accept', 'application/json')
                        
                        with urlopen(detail_req, timeout=5) as detail_response:
                            app_detail = json.loads(detail_response.read().decode('utf-8'))
                            
                            executors = app_detail.get('executors', [])
                            if executors:
                                active_executors = [e for e in executors if e.get('isActive', False)]
                                total_executors += len(active_executors)
                                
                                # Calculer les ressources totales
                                for executor in active_executors:
                                    cores = executor.get('totalCores', 0)
                                    memory = executor.get('maxMemory', 0)
                                    total_cores += cores
                                    total_memory += memory
                                
                                print(f"      └─ Exécuteurs actifs: {len(active_executors)}/{len(executors)}")
                                if active_executors:
                                    print(f"      └─ Cores totaux: {sum(e.get('totalCores', 0) for e in active_executors)}")
                                    memory_mb = sum(e.get('maxMemory', 0) for e in active_executors) / (1024 * 1024)
                                    print(f"      └─ Mémoire totale: {memory_mb:.2f} MB")
                    except Exception as detail_error:
                        # Ignorer les erreurs de détails, ce n'est pas critique
                        pass
                    
                    print()  # Ligne vide entre les applications
                
                # Résumé global
                print(f"📈 Résumé:")
                print(f"   Applications actives: {len([a for a in data if not a.get('attempts', [{}])[-1].get('completed', False)])}")
                print(f"   Applications terminées: {len([a for a in data if a.get('attempts', [{}])[-1].get('completed', False)])}")
                if total_executors > 0:
                    print(f"   Exécuteurs actifs: {total_executors}")
                    print(f"   Cores totaux utilisés: {total_cores}")
                    print(f"   Mémoire totale utilisée: {total_memory / (1024 * 1024):.2f} MB")
                
        except HTTPError as e:
            print(f"❌ Erreur HTTP lors de l'accès à l'API Spark: {e.code} - {e.reason}")
            print(f"   Vérifiez que le Spark Master est accessible sur {spark_ui_url}")
        except URLError as e:
            print(f"❌ Erreur de connexion au Spark Master: {e.reason}")
            print(f"   Vérifiez que le Spark Master est démarré et accessible sur {spark_ui_url}")
            print(f"   Depuis le conteneur Airflow, testez: curl {api_url}")
        except json.JSONDecodeError as e:
            print(f"❌ Erreur de parsing JSON: {e}")
            print(f"   La réponse de l'API n'est pas au format JSON valide")
            # Essayer de lire la réponse pour le débogage
            try:
                req_debug = Request(api_url)
                with urlopen(req_debug, timeout=5) as debug_response:
                    debug_data = debug_response.read().decode('utf-8')
                    print(f"   Réponse reçue (premiers 500 caractères): {debug_data[:500]}")
                    print(f"   Type de contenu: {debug_response.headers.get('Content-Type', 'N/A')}")
            except Exception as debug_error:
                print(f"   Impossible de récupérer la réponse pour débogage: {debug_error}")
        except Exception as e:
            print(f"❌ Erreur lors de la vérification Spark: {e}")
            import traceback
            print(f"   Détails: {traceback.format_exc()}")
            
    except Exception as e:
        print(f"❌ Erreur lors de la vérification Spark: {e}")
        import traceback
        print(traceback.format_exc())


def alert_if_issues(**context):
    """Point central pour alerter (placeholder)."""
    print("Aucune alerte configurée. TODO: brancher email/Slack/Prometheus.")


check_kafka_task = PythonOperator(
    task_id='check_kafka_lag',
    python_callable=check_kafka_lag,
    dag=dag
)

check_minio_task = PythonOperator(
    task_id='check_minio_space',
    python_callable=check_minio_space,
    dag=dag
)

check_spark_task = PythonOperator(
    task_id='check_spark_jobs',
    python_callable=check_spark_jobs,
    dag=dag
)

alert_task = PythonOperator(
    task_id='alert_if_issues',
    python_callable=alert_if_issues,
    dag=dag
)

[check_kafka_task, check_minio_task, check_spark_task] >> alert_task

