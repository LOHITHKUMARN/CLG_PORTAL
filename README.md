# 🎓 College Portal – Academic Management System

A modern **Flask-based web application** built to simplify college administration, internal assessment tracking, attendance monitoring, and academic resource sharing.  
The system provides **separate dashboards for Students and Teachers**, ensuring seamless interaction, efficient data management, and real-time access to academic information.

---

## 🚀 Project Overview

**College Portal** is designed as a dual-portal academic management system that allows:
- Teachers to manage students, enter internal assessment (IA) marks, upload attendance, and share notes.
- Students to view marks, attendance progress, and download subject-wise notes and study materials.

The application includes clean UI dashboards, cloud-ready database integration, secure login authentication, and PDF generation for official reports.

---

## 🧠 Key Features

### 👨‍🏫 **Teacher Features**
- **Branch & Semester Access:** Teachers can log in to their assigned branch and semester.
- **Student Management:**
  - Add students manually or via CSV upload.
  - Edit, update, or reset IA marks and attendance.
- **Marks & Attendance Entry:**
  - Enter IA1, IA2, IA3 marks and attendance per subject.
  - Pre-filled editable forms and reset options.
- **Notes Upload System:**
  - Upload subject-wise notes organized into 5 modules.
  - Notes stored per branch → year → semester → subject → module.
- **Dashboard Management:**
  - Manage data across all semesters (Sem 1–7).
  - Subject lists auto-loaded from `subject_config.py`.
- **PDF Marksheet Generation:**
  - Generate official PDF marksheets with IA marks and attendance summaries.

---

### 👨‍🎓 **Student Features**
- **Secure Login:** Students log in using USN (University Seat Number) and view personal data securely.
- **Marks Dashboard:**
  - View IA1, IA2, and IA3 marks per subject.
  - View attendance data and calculate percentage automatically.
- **Notes Portal:**
  - Access module-wise notes uploaded by teachers.
  - Organized neatly under branch → semester → subject → module.
- **PDF Download:**
  - Download personalized marksheets in PDF format.

---

## 🧩 **Technology Stack**

| Component | Technology |
|------------|-------------|
| **Frontend** | HTML5, CSS3, JavaScript, Bootstrap 5 |
| **Backend** | Flask (Python) |
| **Database** | SQLite (`sem1.db` – `sem7.db` for IA/Attendance) + MongoDB Atlas (for user, branch, and cloud data) |
| **Templating** | Jinja2 |
| **Authentication** | Flask Session-based Login (separate for Students & Teachers) |
| **PDF Generation** | `reportlab` / `xhtml2pdf` |
| **File Storage** | Static Folder (`static/notes/`) organized by branch and semester |

---

## 🗄️ **Database Design**

### SQLite Databases (for IA Marks & Attendance)
Each semester uses its own database (`sem1.db` – `sem7.db`)  
Each DB contains:
- **Table:** `marks`
- **Columns:**  
  `usn`, `name`, `sub1_ia1`, `sub1_ia2`, `sub1_ia3`, `sub1_att1`, `sub1_att2`, `sub1_att3`, … up to `sub6_ia3`, `sub6_att3`

### MongoDB Atlas (for Cloud Storage)
Used for:
- Teacher and student authentication data.
- Branch and year configurations.
- Optional centralized backup and scalability for future extensions.

---

## 🔐 **Authentication System**

- **Teacher Login:**
  - Username/password-based with branch-level password.
  - Session managed using Flask session cookies.
- **Student Login:**
  - USN as username, default password same as USN (can be changed).
  - Sessions isolate student access from teacher data.

Both portals redirect to their respective dashboards after successful authentication.

## 📂 Project Structure

```text
CollegePortal/
+-- app.py
+-- subject_config.py
|
+-- static/
|   +-- css/
|   +-- images/
|   +-- notes/
|
+-- templates/
|   +-- base.html
|   +-- login.html
|   +-- student_dashboard.html
|   +-- teacher_dashboard.html
|   +-- branch_dashboard.html
|   +-- upload_notes.html
|   +-- upload_students.html
|   +-- view_marks.html
|
```


---

## 🌟 **Highlights**

- Responsive and elegant dark theme UI using custom CSS.
- Dynamic animation effects for cards and transitions.
- Toast notifications for success/error messages using **Toastify.js**.
- Modular code design – easy to expand for new branches or semesters.
- Cloud-ready setup via **MongoDB Atlas** for central user and configuration data.

---

## 🧰 **Setup Instructions**

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/college-portal.git
cd college-portal
```
## 2️⃣ Create a Virtual Environment

python -m venv venv
source venv/bin/activate   # (Linux/Mac)
venv\Scripts\activate      # (Windows)

## 3️⃣ Install Dependencies

pip install -r requirements.txt

## 4️⃣ Configure MongoDB Atlas

-Create a MongoDB Atlas cluster.
-Add your connection string in app.py:

client = MongoClient("your_mongodb_atlas_connection_uri")
db = client['college_portal']

## 5️⃣ Run the Application

python app.py
Access it at → http://127.0.0.1:5000

## 🧑‍💻 Future Enhancements

* **📈 Data Visualization:** Interactive dashboards for visualizing marks and attendance stats.
* **🔔 Smart Notifications:** Automated email or in-app notifications for assignment updates.
* **🛡️ Enhanced Security:** Strict Role-Based Access Control (RBAC) for Admins, HODs, Faculty, and Students.
* **☁️ Cloud Scalability:** Moving static assets (notes/PDFs) to Google Drive or Firebase Storage.
* **⚙️ Master Admin Control:** Comprehensive tools for managing branch configurations and user lifecycles.
