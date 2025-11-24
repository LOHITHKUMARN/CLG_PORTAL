import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/college_portal')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    ATTENDANCE_THRESHOLD = float(os.getenv('ATTENDANCE_THRESHOLD', 75.0))
