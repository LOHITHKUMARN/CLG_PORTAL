from pymongo import MongoClient
import certifi

uri = "mongodb+srv://"

try:
    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000
    )
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ Connection failed: {e}")

