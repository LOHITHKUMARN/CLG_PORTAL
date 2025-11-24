from pymongo import MongoClient
import bcrypt

# Connect to MongoDB
client = MongoClient("mongodb+srv://lohithkumar1np_db_user:Lohith0987@cluster0.titokp2.mongodb.net/college_portal?retryWrites=true&w=majority")
db = client['college_portal']
teachers = db['teachers']

# Loop through all teachers
for teacher in teachers.find():
    plain_pw = teacher['password']
    
    # Skip if already hashed (starts with $2b$)
    if plain_pw.startswith("$2b$"):
        continue
    
    # Hash the password
    hashed_pw = bcrypt.hashpw(plain_pw.encode('utf-8'), bcrypt.gensalt())
    
    # Update in DB
    teachers.update_one(
        {"_id": teacher["_id"]},
        {"$set": {"password": hashed_pw.decode('utf-8')}}
    )
    print(f"Updated password for {teacher['username']}")

print("All teacher passwords are now hashed.")
