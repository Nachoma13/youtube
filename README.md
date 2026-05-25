# 🤖 Agente de YouTube Automático — IA & Tecnología en Español

Canal faceless que publica **1 vídeo diario** sobre IA y tecnología en español.
Todo automatizado con herramientas 100% gratuitas.

---

## 📦 Stack de herramientas (todas gratis)

| Paso | Herramienta | Coste |
|------|-------------|-------|
| Guion | Claude API (Sonnet) | Free tier / ~$0.003/video |
| Voz | Microsoft Edge TTS | Gratis (ilimitado) |
| Imágenes/vídeo | Pexels API | Gratis |
| Montaje | MoviePy + ffmpeg | Open source |
| Miniatura | Pillow (Python) | Open source |
| Subida | YouTube Data API v3 | 10.000 unidades/día gratis |
| Automatización | GitHub Actions | 2.000 min/mes gratis |

---

## 🚀 Configuración paso a paso

### 1. Clonar el repo y crear cuenta en GitHub

```bash
git clone https://github.com/TU_USUARIO/youtube-agente-ia.git
cd youtube-agente-ia
```

### 2. Obtener las API Keys

#### Claude API (Anthropic)
1. Ir a https://console.anthropic.com
2. Crear cuenta → API Keys → Nueva clave
3. El tier gratuito incluye créditos iniciales suficientes

#### Pexels API (vídeos libres)
1. Ir a https://www.pexels.com/api/
2. Registrarse → obtener API Key gratis

#### YouTube Data API v3
1. Ir a https://console.cloud.google.com
2. Nuevo proyecto → Habilitar "YouTube Data API v3"
3. Credenciales → OAuth 2.0 → Tipo: Aplicación de escritorio
4. Descargar `client_secret.json`

#### Obtener el Refresh Token de YouTube
Ejecuta este script UNA SOLA VEZ en tu máquina local:

```python
# get_token.py  ─ ejecutar solo una vez
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

print("REFRESH TOKEN:", creds.refresh_token)
print("CLIENT ID:",     creds.client_id)
print("CLIENT SECRET:", creds.client_secret)
```

```bash
pip install google-auth-oauthlib
python get_token.py
```

Autoriza en el navegador → copia los tres valores que imprime.

### 3. Añadir los Secrets en GitHub

Ve a tu repo → **Settings → Secrets and variables → Actions → New secret**

| Nombre del secret | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-... |
| `PEXELS_API_KEY` | Tu API key de Pexels |
| `YOUTUBE_REFRESH_TOKEN` | El refresh token del paso anterior |
| `YOUTUBE_CLIENT_ID` | El client_id |
| `YOUTUBE_CLIENT_SECRET` | El client_secret |

### 4. Activar GitHub Actions

1. Sube el proyecto a GitHub
2. Ve a la pestaña **Actions** → activa los workflows si te lo pide
3. Para probar: **Actions → "Publicar vídeo diario" → Run workflow**

---

## ⏰ Horario de publicación

El archivo `.github/workflows/daily.yml` usa:
```
cron: "0 8 * * *"   # 10:00 AM hora España
```

Modifica la hora a tu gusto usando [crontab.guru](https://crontab.guru).

---

## 🎨 Personalización

En `agent.py` puedes cambiar:

```python
VOICE = "es-ES-AlvaroNeural"   # Voces disponibles: es-MX-JorgeNeural, es-AR-TomasNeural
```

Para cambiar el nicho temático, edita el prompt en `generar_guion()`.

---

## 📊 Registro de vídeos

Cada ejecución guarda una línea en `output/registro.jsonl`:
```json
{"fecha": "20260525_100000", "titulo": "El robot que...", "video_id": "dQw4w9WgXcQ"}
```

---

## ⚠️ Notas importantes

- **YouTube API**: tiene 10.000 unidades/día gratis. Subir 1 vídeo cuesta ~1.600 unidades → perfectamente dentro del límite.
- **Monetización**: YouTube puede tardar 3-6 meses en monetizar un canal nuevo. El contenido generado por IA está permitido siempre que lo declares en la configuración del canal.
- **Calidad**: Para mejorar las miniaturas instala fuentes adicionales o integra Canva API (plan gratuito disponible).
