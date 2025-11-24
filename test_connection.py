from pymongo import MongoClient
import certifi

uri = "mongodb+srv://lohithkumar1np_db_user:Lohith0987@cluster0.titokp2.mongodb.net/?retryWrites=true&w=majority"

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
