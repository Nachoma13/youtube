"""
╔══════════════════════════════════════════════════════════╗
║   AGENTE YOUTUBE AUTOMÁTICO — IA & Tecnología ES        ║
║   Stack: OpenAI · Edge TTS · Pexels · MoviePy · YT API  ║
╚══════════════════════════════════════════════════════════╝

Instalar dependencias:
  pip install openai edge-tts "moviepy==1.0.3" pillow requests \
              google-api-python-client google-auth-oauthlib
"""

import os
import sys
import json
import time
import random
import asyncio
import textwrap
import requests
from pathlib import Path
from datetime import datetime

from openai import OpenAI
import edge_tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip,
    concatenate_videoclips, ColorClip
)
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ══════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════

OPENAI_API_KEY        = os.environ["OPENAI_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

VOICE   = "es-ES-AlvaroNeural"   # Opciones: es-MX-JorgeNeural, es-AR-TomasNeural
VIDEO_W = 1920
VIDEO_H = 1080
FPS     = 24


# ══════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════

def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji}  {msg}", flush=True)


def reintentar(func, intentos=3, espera=5):
    """Ejecuta func hasta 'intentos' veces ante excepciones."""
    for i in range(intentos):
        try:
            return func()
        except Exception as e:
            if i == intentos - 1:
                raise
            log("⚠️", f"Error ({e}), reintentando en {espera}s… ({i+1}/{intentos})")
            time.sleep(espera)


# ══════════════════════════════════════════════
# PASO 1 — GUION CON GPT-4o mini
# ══════════════════════════════════════════════

SYSTEM_PROMPT = """Eres un guionista experto de canales de YouTube faceless en español.
Tu especialidad: vídeos cortos sobre IA, tecnología y ciencia que enganchen desde el primer segundo.
Siempre respondes ÚNICAMENTE con JSON válido, sin markdown, sin texto extra."""

def generar_guion() -> dict:
    """Genera título, guion y metadatos con GPT-4o mini."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    today  = datetime.now().strftime("%d de %B de %Y")

    user_prompt = f"""Fecha actual: {today}

Crea el contenido para UN vídeo de YouTube de 90-120 segundos.
Temática: una curiosidad o historia IMPACTANTE y REAL sobre IA, robótica o tecnología.
Elige el tema más interesante y en tendencia de esta semana.

Devuelve este JSON exacto (sin añadir ni quitar campos):
{{
  "titulo": "Título para YouTube, máx 70 caracteres, con gancho emocional",
  "descripcion": "Descripción YouTube 150-200 chars con 3-4 emojis relevantes",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"],
  "keywords_pexels": ["keyword inglés tema principal", "keyword inglés secundario"],
  "guion": "Texto completo de la voz en off. Entre 220 y 270 palabras. Empieza con una pregunta o dato impactante. Tono divulgativo, cercano y emocionante. No menciones que el vídeo es generado por IA."
}}"""

    def _llamar():
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1200,
            temperature=0.85,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        texto = resp.choices[0].message.content.strip()
        # Limpiar posibles bloques markdown que GPT añada a veces
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto)

    meta = reintentar(_llamar)
    log("📝", f"Título: {meta['titulo']}")
    return meta


# ══════════════════════════════════════════════
# PASO 2 — VOZ CON EDGE TTS (gratis, ilimitado)
# ══════════════════════════════════════════════

async def generar_audio(texto: str, output_path: Path):
    """Convierte el guion a MP3 usando Microsoft Edge TTS."""
    communicate = edge_tts.Communicate(texto, VOICE, rate="+10%", volume="+0%")
    await communicate.save(str(output_path))
    log("🔊", f"Audio listo: {output_path.name} ({output_path.stat().st_size // 1024} KB)")


# ══════════════════════════════════════════════
# PASO 3 — CLIPS DE PEXELS (gratis)
# ══════════════════════════════════════════════

def descargar_clips_pexels(keywords: list[str]) -> list[Path]:
    """Descarga clips HD de Pexels según las keywords del guion."""
    headers = {"Authorization": PEXELS_API_KEY}
    descargados: list[Path] = []

    for kw in keywords[:2]:
        log("🎬", f"Buscando clips: '{kw}'")
        try:
            url  = (f"https://api.pexels.com/videos/search"
                    f"?query={requests.utils.quote(kw)}"
                    f"&per_page=8&orientation=landscape&size=medium")
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            random.shuffle(videos)

            for v in videos[:4]:
                archivos = sorted(
                    v.get("video_files", []),
                    key=lambda x: x.get("width", 0),
                    reverse=True
                )
                # Preferir resolución entre 1280 y 1920 para no sobrecargar
                candidato = next(
                    (f for f in archivos if 1280 <= f.get("width", 0) <= 1920),
                    archivos[0] if archivos else None
                )
                if not candidato:
                    continue

                clip_path = OUTPUT_DIR / f"clip_{v['id']}.mp4"
                if not clip_path.exists():
                    datos = requests.get(candidato["link"], timeout=60).content
                    clip_path.write_bytes(datos)
                    log("  📥", f"{clip_path.name} ({len(datos) // 1024} KB)")

                descargados.append(clip_path)

        except Exception as e:
            log("⚠️", f"Error Pexels ({kw}): {e}")

    if not descargados:
        log("⚠️", "Sin clips de Pexels, se usará fondo de color")
    return descargados


# ══════════════════════════════════════════════
# PASO 4 — MINIATURA CON PILLOW (gratis)
# ══════════════════════════════════════════════

def crear_miniatura(titulo: str, output_path: Path):
    """Genera miniatura 1280×720 con fondo oscuro degradado y texto."""
    W, H = 1280, 720
    img  = Image.new("RGB", (W, H), (8, 8, 18))
    draw = ImageDraw.Draw(img)

    # Degradado vertical morado oscuro → negro
    for y in range(H):
        ratio = y / H
        r = int(40  * (1 - ratio))
        g = int(0   * (1 - ratio))
        b = int(90  * (1 - ratio))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Franja inferior semitransparente
    draw.rectangle([(0, H - 120), (W, H)], fill=(15, 10, 40))

    # Línea decorativa superior
    draw.rectangle([(0, 0), (W, 6)], fill=(120, 60, 255))

    # Fuentes
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_big  = ImageFont.truetype(font_path, 78)
        font_med  = ImageFont.truetype(font_path, 44)
        font_sub  = ImageFont.truetype(font_reg,  34)
    except Exception:
        font_big = font_med = font_sub = ImageFont.load_default()

    # Texto del título (ajuste automático de líneas)
    lineas = textwrap.wrap(titulo, width=20)[:3]
    y_texto = 160 if len(lineas) == 1 else 120
    for linea in lineas:
        draw.text(
            (W // 2, y_texto), linea,
            font=font_big, fill=(255, 255, 255),
            anchor="mm", stroke_width=4, stroke_fill=(60, 0, 140)
        )
        y_texto += 95

    # Etiqueta inferior
    draw.text(
        (W // 2, H - 60), "🤖  IA & Tecnología",
        font=font_sub, fill=(190, 150, 255), anchor="mm"
    )

    # Icono decorativo (círculo con texto "AI")
    cx, cy, r = 100, 100, 52
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(80, 30, 200))
    draw.text((cx, cy), "AI", font=font_med, fill="white", anchor="mm")

    img.save(str(output_path), quality=95)
    log("🖼", f"Miniatura lista: {output_path.name}")


# ══════════════════════════════════════════════
# PASO 5 — MONTAJE CON MOVIEPY (gratis)
# ══════════════════════════════════════════════

def montar_video(clips_paths: list[Path], audio_path: Path, output_path: Path):
    """Une clips de Pexels + audio y exporta el vídeo final."""
    audio           = AudioFileClip(str(audio_path))
    duracion_total  = audio.duration
    log("🎞", f"Duración del audio: {duracion_total:.1f}s")

    segmentos = []
    acumulado = 0.0

    # Repetir la lista de clips si es necesario para cubrir el audio
    fuentes = list(clips_paths) * 4
    random.shuffle(fuentes)

    for cp in fuentes:
        if acumulado >= duracion_total:
            break
        try:
            clip = VideoFileClip(str(cp))
            # Recortar fragmentos de 5-12 segundos para más dinamismo
            inicio    = random.uniform(0, max(0, clip.duration - 5))
            max_dur   = min(12.0, clip.duration - inicio)
            frag_dur  = min(max_dur, duracion_total - acumulado)
            if frag_dur < 1.0:
                clip.close()
                continue

            frag = (clip
                    .subclip(inicio, inicio + frag_dur)
                    .resize((VIDEO_W, VIDEO_H)))
            segmentos.append(frag)
            acumulado += frag_dur
            log("  ✂️", f"{cp.name} → fragmento {frag_dur:.1f}s")
            clip.close()

        except Exception as e:
            log("⚠️", f"Error con {cp.name}: {e}")

    # Fallback si no hay clips válidos
    if not segmentos:
        log("⚠️", "Sin clips válidos, generando fondo de color")
        segmentos = [ColorClip(
            size=(VIDEO_W, VIDEO_H),
            color=(8, 8, 18),
            duration=duracion_total
        )]

    video_base = concatenate_videoclips(segmentos, method="compose")
    video_final = video_base.set_audio(audio)

    video_final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23"],
    )
    log("✅", f"Vídeo listo: {output_path.name}")

    # Liberar memoria
    video_final.close()
    audio.close()


# ══════════════════════════════════════════════
# PASO 6 — SUBIDA A YOUTUBE (gratis, cuota 10k/día)
# ══════════════════════════════════════════════

def obtener_credenciales_youtube() -> Credentials:
    """Construye y refresca las credenciales OAuth de YouTube."""
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"],
    )
    creds.refresh(Request())
    return creds


def subir_a_youtube(video_path: Path, thumb_path: Path, meta: dict) -> str:
    """Sube el vídeo y la miniatura a YouTube."""
    creds   = obtener_credenciales_youtube()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    descripcion_completa = (
        meta["descripcion"] + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 Suscríbete para más curiosidades de IA cada día\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "#IA #InteligenciaArtificial #Tecnologia #Curiosidades #CienciaYTecnologia"
    )

    body = {
        "snippet": {
            "title":           meta["titulo"],
            "description":     descripcion_completa,
            "tags":            meta["tags"] + ["IA", "inteligencia artificial",
                                               "tecnología", "curiosidades", "ciencia"],
            "categoryId":      "28",   # Ciencia y tecnología
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus":          "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }

    media   = MediaFileUpload(str(video_path), mimetype="video/mp4",
                              chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    log("📤", "Subiendo vídeo…")
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            log("  ↑", f"{pct}%")

    video_id = response["id"]
    log("✅", f"Publicado → https://youtu.be/{video_id}")

    # Subir miniatura
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
        ).execute()
        log("🖼", "Miniatura personalizada subida")
    except Exception as e:
        log("⚠️", f"No se pudo subir miniatura: {e}")

    return video_id


# ══════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════

async def main():
    inicio = time.time()
    fecha  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log("🚀", f"Agente iniciado — {fecha}")
    print("─" * 55)

    try:
        # 1. Guion
        log("1/6", "Generando guion con GPT-4o mini…")
        meta = generar_guion()

        # 2. Audio
        log("2/6", "Generando voz con Edge TTS…")
        audio_path = OUTPUT_DIR / f"audio_{fecha}.mp3"
        await generar_audio(meta["guion"], audio_path)

        # 3. Clips
        log("3/6", "Descargando clips de Pexels…")
        clips = descargar_clips_pexels(meta["keywords_pexels"])

        # 4. Miniatura
        log("4/6", "Creando miniatura…")
        thumb_path = OUTPUT_DIR / f"thumb_{fecha}.jpg"
        crear_miniatura(meta["titulo"], thumb_path)

        # 5. Montar vídeo
        log("5/6", "Montando vídeo…")
        video_path = OUTPUT_DIR / f"video_{fecha}.mp4"
        montar_video(clips, audio_path, video_path)

        # 6. Subir
        log("6/6", "Subiendo a YouTube…")
        video_id = subir_a_youtube(video_path, thumb_path, meta)

        # Registro
        registro = {
            "fecha":    fecha,
            "titulo":   meta["titulo"],
            "video_id": video_id,
            "url":      f"https://youtu.be/{video_id}",
        }
        with open(OUTPUT_DIR / "registro.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

        print("─" * 55)
        elapsed = int(time.time() - inicio)
        log("🎉", f"¡Listo en {elapsed}s! → https://youtu.be/{video_id}")

    except Exception as e:
        log("❌", f"Error fatal: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
