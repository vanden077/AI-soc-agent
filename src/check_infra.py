# import json
# import urllib.request
#
# import redis
#
# print("🔍 Checking infrastructure connectivity and storage health...\n")
#
# # 1. Test connection to the Redis container
# try:
#     # Connect using credentials defined in the docker-compose configuration
#     r = redis.Redis(
#         host="localhost",
#         port=6379,
#         password="RedisSecurePass456!",
#         decode_responses=True,
#     )
#     r.ping()
#     print("✅ [REDIS] : Connection successfully established.")
#
#     # Rapid write/read check to validate operational persistence
#     r.set("soc_agent_health", "OK")
#     if r.get("soc_agent_health") == "OK":
#         print("✅ [REDIS] : Write/Read persistence capability verified.")
# except Exception as e:  # noqa: BLE001
#     print(f"❌ [REDIS] : Connection failure. Error: {e}")
#
# # 2. Test connection to the Ollama container and inventory local models
# try:
#     # Use native REST API tags endpoint to check availability
#     req = urllib.request.Request("http://localhost:11434/api/tags")
#     with urllib.request.urlopen(req) as response:
#         if response.status == 200:
#             data = json.loads(response.read().decode())
#             print("✅ [OLLAMA] : Inference server is reachable.")
#
#             # Extract model tags existing inside the docker volume
#             models: list[str] = [m["name"] for m in data.get("models", [])]
#             if models:
#                 print(f"📦 [OLLAMA] : Available local models: {models}")
#             else:
#                 print(
#                     "⚠️  [OLLAMA] : No models pulled yet. Please run 'ollama run llama3.1' inside the container."
#                 )
# except Exception as e:  # noqa: BLE001
#     print(f"❌ [OLLAMA] : Inference server unreachable. Error: {e}")
