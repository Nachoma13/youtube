"""
Ejecuta este script UNA SOLA VEZ en tu máquina local para obtener
el refresh token de YouTube que necesitas como GitHub Secret.

Requisitos:
  pip install google-auth-oauthlib

Uso:
  1. Descarga tu client_secret.json desde Google Cloud Console
  2. Colócalo en la misma carpeta que este script
  3. python get_youtube_token.py
  4. Copia los valores que imprime y añádelos como GitHub Secrets
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

print("\n" + "="*60)
print("✅ COPIA ESTOS VALORES COMO GITHUB SECRETS:")
print("="*60)
print(f"YOUTUBE_REFRESH_TOKEN  →  {creds.refresh_token}")
print(f"YOUTUBE_CLIENT_ID      →  {creds.client_id}")
print(f"YOUTUBE_CLIENT_SECRET  →  {creds.client_secret}")
print("="*60 + "\n")
