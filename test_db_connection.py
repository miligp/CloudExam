import pyodbc

server = 'galleryserver.database.windows.net'
database = 'GalleryBD'
username = 'azureuser@galleryserver'
password = '{MiSaTiFa12!*}'
driver= '{ODBC Driver 18 for SQL Server}'

try:
    conn = pyodbc.connect(
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"PORT=1433;"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    print("Connexion réussie !")
    conn.close()
except Exception as e:
    print(f"Erreur de connexion : {e}")
