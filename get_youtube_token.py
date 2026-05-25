"""
╔══════════════════════════════════════════════════════════╗
║   OBTENER TOKEN DE YOUTUBE — ejecutar UNA sola vez      ║
║   en tu PC antes de subir el proyecto a GitHub          ║
╚══════════════════════════════════════════════════════════╝

PASOS:
  1. Ve a https://console.cloud.google.com
  2. Nuevo proyecto → Habilitar "YouTube Data API v3"
  3. Credenciales → Crear → ID de cliente OAuth 2.0
     Tipo: Aplicación de escritorio
  4. Descargar el archivo → guardarlo como "client_secret.json"
     en la misma carpeta que este script
  5. Ejecutar:
       pip install google-auth-oauthlib
       python get_youtube_token.py
  6. Se abrirá el navegador → autoriza con tu cuenta de YouTube
  7. Copia los 3 valores que imprime y añádelos como GitHub Secrets
"""

import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ Falta la librería. Ejecuta primero:")
    print("   pip install google-auth-oauthlib")
    sys.exit(1)

SECRET_FILE = Path("client_secret.json")

if not SECRET_FILE.exists():
    print("❌ No se encuentra 'client_secret.json' en esta carpeta.")
    print("   Descárgalo desde Google Cloud Console → Credenciales → tu OAuth 2.0 client.")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

print("🌐 Abriendo el navegador para autorizar el acceso a YouTube…")
print("   (Si no se abre solo, copia la URL que aparece en la terminal)\n")

flow  = InstalledAppFlow.from_client_secrets_file(str(SECRET_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

print("\n" + "═" * 60)
print("✅  COPIA ESTOS 3 VALORES COMO SECRETS EN GITHUB")
print("    Repo → Settings → Secrets and variables → Actions")
print("═" * 60)
print(f"\n  YOUTUBE_REFRESH_TOKEN  →  {creds.refresh_token}")
print(f"  YOUTUBE_CLIENT_ID      →  {creds.client_id}")
print(f"  YOUTUBE_CLIENT_SECRET  →  {creds.client_secret}")
print("\n" + "═" * 60)

# También guardar en archivo local por si acaso
salida = {
    "YOUTUBE_REFRESH_TOKEN":  creds.refresh_token,
    "YOUTUBE_CLIENT_ID":      creds.client_id,
    "YOUTUBE_CLIENT_SECRET":  creds.client_secret,
}
Path("youtube_secrets.json").write_text(
    json.dumps(salida, indent=2), encoding="utf-8"
)
print("\n💾  También guardado en: youtube_secrets.json")
print("    ⚠️  NO subas ese archivo a GitHub (añádelo al .gitignore)\n")
