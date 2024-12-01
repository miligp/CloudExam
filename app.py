from flask import Flask, request, render_template, redirect, url_for, session, flash
import os
import pyodbc
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
import re
from collections import namedtuple

# Charger les variables d'environnement
load_dotenv()




# Configurations Flask
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

# Initialisation Flask-Bcrypt
bcrypt = Bcrypt(app)
# Configurations Azure
AZURE_CONNECTION_STRING = os.getenv('AZURE_CONNECTION_STRING')
DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
CONTAINER_NAME = "gallery-photos"

# Initialisation Azure Blob Storage
try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    if not container_client.exists():
        container_client.create_container()
        print(f"Container '{CONTAINER_NAME}' créé.")
    else:
        print(f"Connexion réussie au container : {CONTAINER_NAME}")
except Exception as e:
    raise RuntimeError(f"Erreur de configuration Blob Storage : {e}")


# Fonction pour se connecter à la base de données SQL
def get_db_connection():
    try:
        conn = pyodbc.connect(
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={DATABASE_URL};"
            f"DATABASE=GalleryBD;"
            f"UID={DATABASE_USER};"
            f"PWD={DATABASE_PASSWORD};"
            f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )
        return conn
    except Exception as e:
        raise RuntimeError(f"Erreur de connexion à la base SQL : {e}")


# Route pour afficher la galerie
@app.route('/')
def home():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_url, user_id FROM photos")
        # Créer une structure nommée pour chaque photo
        Photo = namedtuple('Photo', ['id', 'file_url', 'user_id'])
        photos = [Photo(*row) for row in cursor.fetchall()]  # Transforme chaque ligne en Photo
        conn.close()
        return render_template('index.html', photos=photos, current_user=session.get('user_id'))
    except Exception as e:
        app.logger.error(f"Erreur d'accès au container : {e}")
        return render_template('error.html', message="Impossible d'accéder à la galerie.")


# Route d'inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not username or not email or not password:
            flash("Tous les champs sont obligatoires.", "error")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
            return redirect(url_for('register'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Email invalide.", "error")
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, hashed_password)
            )
            conn.commit()
            conn.close()
            flash("Inscription réussie ! Connectez-vous maintenant.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("Erreur lors de l'inscription. Veuillez réessayer.", "error")
            app.logger.error(f"Erreur lors de l'inscription : {e}")
            return redirect(url_for('register'))

    return render_template('register.html')


# Route de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            conn.close()

            if user and bcrypt.check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash("Connexion réussie !", "success")
                return redirect(url_for('home'))
            else:
                flash("Email ou mot de passe incorrect.", "error")
                return redirect(url_for('login'))
        except Exception as e:
            flash("Erreur lors de la connexion. Veuillez réessayer.", "error")
            app.logger.error(f"Erreur lors de la connexion : {e}")
            return redirect(url_for('login'))

    return render_template('login.html')


# Route de déconnexion
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Supprime toutes les données de session
    flash("Vous avez été déconnecté avec succès.", "success")
    return redirect(url_for('login'))  # Redirige vers la page de connexion

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files.get('photo')
        if file:
            try:
                # Connexion au container
                blob_client = container_client.get_blob_client(file.filename)

                # Upload du fichier
                blob_client.upload_blob(file.read(), overwrite=True)

                # Ajout à la base de données
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO photos (file_url, user_id) VALUES (?, ?)",
                    (f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{file.filename}",
                     session.get('user_id'))
                )
                conn.commit()
                conn.close()

                flash("Photo uploadée avec succès.", "success")
                return redirect(url_for('home'))
            except Exception as e:
                app.logger.error(f"Erreur lors de l'upload : {e}")
                return render_template('error.html', message="Erreur lors de l'upload.")
        else:
            return render_template('error.html', message="Aucun fichier sélectionné.")
    return render_template('upload.html')



@app.route('/error')
def error_page():
    return render_template('error.html', message="Une erreur inattendue est survenue.")

@app.route('/users')
def users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        conn.close()
        return render_template('users.html', users=users)
    except Exception as e:
        app.logger.error(f"Erreur lors de la récupération des utilisateurs : {e}")
        return render_template('error.html', message="Impossible de récupérer les utilisateurs.")

@app.route('/delete/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    try:
        # Vérifie si l'utilisateur est connecté
        if not session.get('user_id'):
            flash("Vous devez être connecté pour supprimer une photo.", "error")
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Vérifie si l'utilisateur est le propriétaire de la photo
        cursor.execute("SELECT file_url, user_id FROM photos WHERE id = ?", (photo_id,))
        photo = cursor.fetchone()

        if not photo:
            flash("Photo introuvable.", "error")
            return redirect(url_for('home'))

        if photo.user_id != session['user_id']:
            flash("Vous n'êtes pas autorisé à supprimer cette photo.", "error")
            return redirect(url_for('home'))

        # Supprime la photo de Blob Storage
        blob_name = photo.file_url.split("/")[-1]
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.delete_blob()

        # Supprime la photo de la base de données
        cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()
        conn.close()

        flash("Photo supprimée avec succès.", "success")
        return redirect(url_for('home'))
    except Exception as e:
        app.logger.error(f"Erreur lors de la suppression de la photo : {e}")
        return render_template('error.html', message="Impossible de supprimer la photo.")

if __name__ == '__main__':
    app.run(debug=True)
