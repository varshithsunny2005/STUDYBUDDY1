# StudyBuddy


[![Live Demo – Render](https://img.shields.io/badge/Live%20Demo-StudyBuddy-green?style=flat&logo=render)](https://studybuddy-stdl.onrender.com)

StudyBuddy is a full-stack, real-time collaborative web application that enables students to create and participate in topic-based study rooms.
Built with Django and Supabase, it supports live group messaging, dynamic participant tracking, and avatar-based user profiles. The platform leverages Supabase Realtime for instant message delivery, Supabase Storage for media management, and PostgreSQL for scalable data handling — all within a modern, responsive, and secure user interface.

---


##  Key Features

- **User Authentication**: Register, login, and manage your profile.
- **Profile Avatars**: Upload avatars (stored on Supabase Storage) with robust default/fallback handling.
- **Study Rooms**: Create, join, and participate in themed study rooms.
- **Real-Time Chat**: Instant messaging in rooms using Supabase Realtime.
- **Live Participants List**: See who is currently in each room, updated in real time.
- **Topic Browsing**: Discover and filter rooms by topics.
- **Recent Activities Feed**: View the latest messages and activities across the platform.
- **Responsive UI**: Clean, modern interface with mobile support.
- **Secure**: CSRF protection, permission checks, and no sensitive data in logs.

---

##  Technologies Used

- **Backend**: Django 4.x, Django REST Framework
- **Frontend**: Django Templates, HTML, CSS, JavaScript
- **Database & Storage**: Supabase (Postgres, Storage, Realtime)
- **Static Files**: WhiteNoise
- **Deployment**: Render.com
- **Other**: python-dotenv, Gunicorn, CORS Headers

---

##  Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Bhargavzz/StudyBuddy.git
   cd StudyBuddy/studybud
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # On Windows:
   .\.venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**  
   Create a `.env` file in the `studybud` directory with the following variables (see below).

5. **Run migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Collect static files:**
   ```bash
   python manage.py collectstatic
   ```

7. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

8. **Visit** [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

##  Environment Variables

Create a `.env` file in your `studybud` directory with the following keys:

```env
DJANGO_SECRET_KEY=your-django-secret-key
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
DB_NAME=your_db_name         # Only if using a local/other Postgres DB
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=your_db_port
```

> **Note:** If you use only Supabase for all data, you may not need the DB_* variables.

---

##  Deployment (Render.com)

Live Demo: [https://studybuddy-stdl.onrender.com](https://studybuddy-stdl.onrender.com)

1. **Push your code to GitHub.**
2. **Create a new Web Service** on [Render](https://dashboard.render.com/):
   - Set the **Root Directory** to `studybud`
   - **Build Command:**  
     ```
     pip install -r requirements.txt; python manage.py collectstatic --noinput
     ```
   - **Start Command:**  
     ```
     gunicorn studybud.wsgi
     ```
   - **Environment Variables:**  
     Add all variables from your `.env` file in the Render dashboard.
   - **ALLOWED_HOSTS:**  
     Add your Render URL (`studybuddy-stdl.onrender.com`) to `ALLOWED_HOSTS` in `settings.py`.
3. **Redeploy** after any settings change.

---

##  API Routes & Usage

- **Room Participants (AJAX/Realtime):**
  ```
  GET /api/room/<room_id>/participants/
  ```
  Returns a JSON list of participants with `id`, `name`, `username`, and `avatar_url`.

- **Room Messaging (POST):**
  ```
  POST /room/<room_id>/
  body: { body: "Your message" }
  ```
  Authenticated users can post messages to a room.

- **User Profile:**
  ```
  GET /profile/<user_id>/
  ```

- **Other endpoints** are handled via Django views and templates.

---

##  Contribution Guidelines

- Fork the repository and create a new branch for your feature or bugfix.
- Follow PEP8 and Django best practices.
- Submit a pull request with a clear description of your changes.
- For major changes, open an issue first to discuss what you’d like to change.

---



##  Acknowledgements

- [Supabase](https://supabase.com/) for backend, storage, and realtime.
- [Render](https://render.com/) for easy Django deployment.
- Django, DRF, and the open-source community.

---
##  Author
**Sitra Vishnu Bhargav**  
Final-year CSE, IIIT Jabalpur  
[GitHub](https://github.com/Bhargavzz) • [LinkedIn](https://linkedin.com/in/bhargavzz)