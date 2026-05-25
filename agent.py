"""
Agente de YouTube Automático
Temática: Curiosidades e Historias de IA en Español
Herramientas: Claude API + Edge TTS + Pexels + MoviePy + YouTube API
"""

import os
import json
import random
import asyncio
import requests
import textwrap
from pathlib import Path
from datetime import datetime

# ── pip install anthropic edge-tts moviepy pillow google-api-python-client google-auth-oauthlib
import anthropic
import edge_tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips, ColorClip
)
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]   # secret en GitHub Actions
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]       # gratis en pexels.com/api
YOUTUBE_TOKEN     = os.environ["YOUTUBE_REFRESH_TOKEN"] # ver README

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

VOICE       = "es-ES-AlvaroNeural"   # Edge TTS — voz masculina española
VIDEO_W     = 1920
VIDEO_H     = 1080
FPS         = 24
MAX_CLIPS   = 6   # clips de Pexels a combinar


# ─────────────────────────────────────────────
# PASO 1 — GENERAR GUION CON CLAUDE
# ─────────────────────────────────────────────
def generar_guion() -> dict:
    """Pide a Claude un tema trending + guion de ~90 segundos."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = datetime.now().strftime("%d de %B de %Y")
    prompt = f"""Hoy es {today}. Eres un guionista de YouTube especializado en IA y tecnología en español.

Crea un vídeo corto (90-120 segundos, estilo canal faceless) sobre UNA curiosidad o historia impactante
relacionada con inteligencia artificial, robótica o tecnología. Elige un tema que esté en tendencia esta semana.

Responde SOLO con un JSON válido (sin markdown, sin explicaciones) con esta estructura exacta:
{{
  "titulo": "Título llamativo para YouTube (máx 70 caracteres)",
  "descripcion": "Descripción para YouTube con emojis (150-200 caracteres)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "keywords_pexels": ["keyword1 en inglés", "keyword2 en inglés"],
  "guion": "El texto completo que leerá la voz en off. Mínimo 200 palabras, máximo 280. Tono divulgativo y emocionante. Sin mencionar que es IA generada."
}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    return json.loads(raw)


# ─────────────────────────────────────────────
# PASO 2 — GENERAR VOZ CON EDGE TTS (gratis)
# ─────────────────────────────────────────────
async def generar_audio(texto: str, output_path: Path):
    """Convierte el guion a MP3 con Microsoft Edge TTS."""
    communicate = edge_tts.Communicate(texto, VOICE, rate="+8%")
    await communicate.save(str(output_path))
    print(f"✅ Audio generado: {output_path}")


# ─────────────────────────────────────────────
# PASO 3 — DESCARGAR CLIPS DE PEXELS (gratis)
# ─────────────────────────────────────────────
def descargar_clips_pexels(keywords: list[str]) -> list[Path]:
    """Descarga clips HD de Pexels según las keywords del guion."""
    headers = {"Authorization": PEXELS_API_KEY}
    clips_descargados = []

    for kw in keywords[:2]:
        url = f"https://api.pexels.com/videos/search?query={kw}&per_page={MAX_CLIPS}&orientation=landscape"
        resp = requests.get(url, headers=headers, timeout=15)
        videos = resp.json().get("videos", [])
        random.shuffle(videos)

        for v in videos[:3]:
            # Elegir la versión HD (1280x720 o similar)
            archivos = sorted(v["video_files"], key=lambda x: x.get("width", 0), reverse=True)
            hd = next((f for f in archivos if f.get("width", 0) >= 1280), archivos[0])
            clip_path = OUTPUT_DIR / f"clip_{v['id']}.mp4"

            if not clip_path.exists():
                datos = requests.get(hd["link"], timeout=30).content
                clip_path.write_bytes(datos)
                print(f"  📥 Clip descargado: {clip_path.name}")

            clips_descargados.append(clip_path)

    return clips_descargados


# ─────────────────────────────────────────────
# PASO 4 — MINIATURA CON PILLOW (gratis)
# ─────────────────────────────────────────────
def crear_miniatura(titulo: str, output_path: Path):
    """Genera una miniatura 1280x720 con gradiente y texto."""
    img = Image.new("RGB", (1280, 720), color=(10, 10, 20))
    draw = ImageDraw.Draw(img)

    # Fondo con gradiente simple (barras de opacidad)
    for i in range(720):
        alpha = int(80 * (1 - i / 720))
        draw.line([(0, i), (1280, i)], fill=(30, 0, 80, alpha))

    # Franja de color inferior
    draw.rectangle([(0, 580), (1280, 720)], fill=(20, 20, 60))

    # Texto principal
    try:
        font_big   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except Exception:
        font_big   = ImageFont.load_default()
        font_small = font_big

    # Ajuste de líneas
    lineas = textwrap.wrap(titulo, width=22)
    y = 200
    for linea in lineas[:3]:
        draw.text((640, y), linea, font=font_big, fill="white", anchor="mm",
                  stroke_width=3, stroke_fill=(80, 0, 180))
        y += 90

    draw.text((640, 660), "🤖 IA & Tecnología", font=font_small, fill=(180, 140, 255), anchor="mm")

    img.save(str(output_path))
    print(f"✅ Miniatura: {output_path}")


# ─────────────────────────────────────────────
# PASO 5 — MONTAR VÍDEO CON MOVIEPY (gratis)
# ─────────────────────────────────────────────
def montar_video(clips_paths: list[Path], audio_path: Path, output_path: Path):
    """Combina clips de Pexels con la voz en off."""
    audio = AudioFileClip(str(audio_path))
    duracion_total = audio.duration

    # Cargar y recortar clips hasta llenar la duración del audio
    segmentos = []
    tiempo_acumulado = 0
    for cp in clips_paths * 3:   # repetir lista si hay pocos clips
        if tiempo_acumulado >= duracion_total:
            break
        try:
            clip = VideoFileClip(str(cp)).resize((VIDEO_W, VIDEO_H))
            segmento_dur = min(clip.duration, duracion_total - tiempo_acumulado)
            segmentos.append(clip.subclip(0, segmento_dur))
            tiempo_acumulado += segmento_dur
        except Exception as e:
            print(f"  ⚠️ Error con clip {cp}: {e}")

    if not segmentos:
        # Fallback: fondo negro
        segmentos = [ColorClip(size=(VIDEO_W, VIDEO_H), color=[10, 10, 20], duration=duracion_total)]

    video = concatenate_videoclips(segmentos, method="compose")
    video = video.set_audio(audio)
    video.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None
    )
    print(f"✅ Vídeo montado: {output_path}")


# ─────────────────────────────────────────────
# PASO 6 — SUBIR A YOUTUBE (gratis con cuota)
# ─────────────────────────────────────────────
def subir_a_youtube(video_path: Path, thumb_path: Path, meta: dict):
    """Sube el vídeo a YouTube con la Data API v3."""
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": meta["titulo"],
            "description": meta["descripcion"] + "\n\n#IA #Tecnologia #Inteligencia #Artificial",
            "tags": meta["tags"] + ["IA", "inteligencia artificial", "tecnología", "curiosidades"],
            "categoryId": "28",   # Ciencia y tecnología
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  📤 Subiendo... {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ Vídeo publicado: https://youtu.be/{video_id}")

    # Subir miniatura
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumb_path))
    ).execute()
    print("✅ Miniatura subida")
    return video_id


# ─────────────────────────────────────────────
# MAIN — PIPELINE COMPLETO
# ─────────────────────────────────────────────
async def main():
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n🚀 Iniciando agente — {fecha}\n")

    # 1. Guion
    print("📝 Generando guion con Claude...")
    meta = generar_guion()
    print(f"   Título: {meta['titulo']}")

    # 2. Audio
    audio_path = OUTPUT_DIR / f"audio_{fecha}.mp3"
    print("🔊 Generando voz...")
    await generar_audio(meta["guion"], audio_path)

    # 3. Clips
    print("🎬 Descargando clips de Pexels...")
    clips = descargar_clips_pexels(meta["keywords_pexels"])

    # 4. Miniatura
    thumb_path = OUTPUT_DIR / f"thumb_{fecha}.jpg"
    print("🖼  Creando miniatura...")
    crear_miniatura(meta["titulo"], thumb_path)

    # 5. Montar vídeo
    video_path = OUTPUT_DIR / f"video_{fecha}.mp4"
    print("🎞  Montando vídeo...")
    montar_video(clips, audio_path, video_path)

    # 6. Subir
    print("📤 Subiendo a YouTube...")
    video_id = subir_a_youtube(video_path, thumb_path, meta)

    # Guardar registro
    log = {"fecha": fecha, "titulo": meta["titulo"], "video_id": video_id}
    with open(OUTPUT_DIR / "registro.jsonl", "a") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")

    print(f"\n🎉 ¡Listo! https://youtu.be/{video_id}\n")


if __name__ == "__main__":
    asyncio.run(main())
