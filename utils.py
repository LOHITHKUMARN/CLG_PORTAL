import os
from werkzeug.utils import secure_filename
from datetime import datetime
import bcrypt

# -------------------- Allowed File Types -------------------- #
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'zip'}


def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file_obj, upload_folder, subpath=''):
    """
    Save uploaded file to a folder and return the relative path.
    Automatically creates subfolders and timestamps filenames.
    """
    if not file_obj or file_obj.filename == '':
        return None
    if not allowed_file(file_obj.filename):
        return None

    filename = secure_filename(file_obj.filename)
    folder = os.path.join(upload_folder, subpath)
    os.makedirs(folder, exist_ok=True)

    # Append timestamp to avoid overwriting files
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filepath = os.path.join(folder, f"{timestamp}_{filename}")

    # Save file safely
    try:
        file_obj.save(filepath)
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None

    # Return relative path (for Flask static serving)
    return filepath.replace("\\", "/")


# -------------------- Password Utilities -------------------- #
def hash_password(password: str) -> str:
    """
    Hash a plain password with bcrypt and return a UTF-8 string.
    This string can be stored safely in MongoDB.
    """
    if not password:
        return None
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')


def check_password(plain_password: str, hashed_password) -> bool:
    """
    Verify a plain password against the stored hash.
    Works whether hashed_password is str (from DB) or bytes.
    """
    if not plain_password or not hashed_password:
        return False

    if isinstance(hashed_password, str):
        hashed_bytes = hashed_password.encode('utf-8')
    else:
        hashed_bytes = hashed_password

    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_bytes)
    except Exception as e:
        print(f"❌ Password check failed: {e}")
        return False


# -------------------- GPA & Attendance Utilities -------------------- #
def calc_gpa(marks_list):
    """
    Calculate GPA based on IA1, IA2, IA3 marks per subject.

    marks_list: list of dicts, each having keys:
        IA1, IA2, IA3, max_marks (default=30), subject, semester

    Formula:
        Average percentage across all subjects ÷ 10
    Example:
        If avg percentage = 82%, GPA = 8.2
    """
    if not marks_list:
        return 0.0

    percentages = []
    for m in marks_list:
        try:
            ia1 = int(m.get('IA1', 0) or 0)
            ia2 = int(m.get('IA2', 0) or 0)
            ia3 = int(m.get('IA3', 0) or 0)
            max_marks = int(m.get('max_marks', 30) or 30)
            total_max = max_marks * 3
            perc = (ia1 + ia2 + ia3) / total_max * 100 if total_max else 0
            percentages.append(perc)
        except Exception:
            percentages.append(0)

    avg_percent = sum(percentages) / len(percentages)
    return round(avg_percent / 10, 2)


def calc_attendance_percentage(classes_held, classes_attended):
    """
    Calculate attendance percentage safely.
    """
    try:
        if not classes_held or int(classes_held) == 0:
            return 0.0
        return round((int(classes_attended) / int(classes_held)) * 100, 2)
    except Exception:
        return 0.0
