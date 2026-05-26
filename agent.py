"""
╔══════════════════════════════════════════════════════════╗
║   AGENTE YOUTUBE — Historias IA · 5 vídeos por lote     ║
║   Stack: Groq · Pollinations · Edge TTS · ffmpeg · YT   ║
╚══════════════════════════════════════════════════════════╝
"""
 
import os
import json
import time
import random
import asyncio
import textwrap
import subprocess
import requests
import urllib.parse
from pathlib import Path
from datetime import datetime
 
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
 
# ══════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════
 
GROQ_API_KEY          = os.environ["GROQ_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
 
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
 
VOICE      = "es-ES-AlvaroNeural"
VIDEO_W    = 1920
VIDEO_H    = 1080
FPS        = 24
VIDEOS_POR_LOTE = 5
 
GENEROS = [
    "terror y misterio paranormal",
    "curiosidades impactantes de inteligencia artificial",
    "historias motivacionales de éxito contra todo pronóstico",
    "misterios sin resolver de la historia y el universo",
    "tecnología del futuro que ya existe hoy",
    "historias reales más increíbles de la ciencia",
    "fenómenos inexplicables y conspiración",
    "historias de supervivencia extrema",
]
 
VOCES_ES = [
    "es-ES-AlvaroNeural",
    "es-ES-ElviraNeural",
    "es-MX-JorgeNeural",
    "es-AR-TomasNeural",
]
 
 
# ══════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════
 
def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji}  {msg}", flush=True)
 
 
def reintentar(func, intentos=3, espera=8):
    for i in range(intentos):
        try:
            return func()
        except Exception as e:
            if i == intentos - 1:
                raise
            log("⚠️", f"Reintentando ({i+1}/{intentos}): {str(e)[:80]}")
            time.sleep(espera)
 
 
def ffmpeg_run(*args):
    cmd    = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg: {result.stderr[-400:]}")
 
 
def duracion_audio(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 90.0
 
 
# ══════════════════════════════════════════════
# PASO 1 — GUION CON GROQ
# ══════════════════════════════════════════════
 
def generar_guion(genero: str, indice: int) -> dict:
    today = datetime.now().strftime("%d de %B de %Y")
 
    prompt = f"""Fecha: {today}. Vídeo #{indice+1} del día.
 
Eres un guionista viral de YouTube en español. Crea un vídeo del género: "{genero}".
El vídeo dura entre 90 y 120 segundos. Debe ser adictivo desde la primera frase.
 
Responde SOLO con este JSON válido (sin markdown, sin texto extra):
{{
  "titulo": "Título YouTube máx 70 chars, con gancho fuerte, usa números o preguntas",
  "descripcion": "Descripción 150-200 chars con emojis temáticos",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7"],
  "prompts_imagenes": [
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 1",
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 2",
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 3",
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 4",
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 5",
    "cinematic scene prompt in english for AI image generation, detailed, 4k, scene 6"
  ],
  "guion": "Texto voz en off: 220-270 palabras. Primera frase impactante. Ritmo rápido. No menciones que es IA generado."
}}"""
 
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model":       "llama-3.3-70b-versatile",
        "messages":    [
            {"role": "system", "content": "Guionista experto YouTube. Responde SOLO JSON válido sin markdown."},
            {"role": "user",   "content": prompt}
        ],
        "temperature": 0.9,
        "max_tokens":  1500,
    }
 
    def _llamar():
        resp  = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in texto:
            partes = texto.split("```")
            texto  = partes[1] if len(partes) > 1 else partes[0]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto.strip())
 
    meta = reintentar(_llamar)
    log("📝", f"[{indice+1}/5] {meta['titulo']}")
    return meta
 
 
# ══════════════════════════════════════════════
# PASO 2 — IMÁGENES IA CON POLLINATIONS (gratis)
# ══════════════════════════════════════════════
 
def generar_imagen_ia(prompt: str, output_path: Path, idx: int):
    """Genera imagen cinematográfica con Pollinations.ai (gratis, sin API key)."""
    prompt_limpio = prompt[:400].replace("\n", " ")
    prompt_enc    = urllib.parse.quote(prompt_limpio)
 
    # Añadir estilo cinematográfico al prompt
    estilo = "cinematic, dramatic lighting, 8k, ultra detailed, photorealistic"
    url    = (f"https://image.pollinations.ai/prompt/{prompt_enc}%2C{urllib.parse.quote(estilo)}"
              f"?width={VIDEO_W}&height={VIDEO_H}&nologo=true&seed={random.randint(1,99999)}")
 
    def _descargar():
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        if len(resp.content) < 5000:
            raise ValueError("Imagen demasiado pequeña, reintentando")
        output_path.write_bytes(resp.content)
 
    try:
        reintentar(_descargar, intentos=3, espera=5)
        log("  🎨", f"Imagen {idx+1} generada ({output_path.stat().st_size // 1024} KB)")
    except Exception as e:
        log("  ⚠️", f"Imagen {idx+1} fallida ({e}), usando fondo de color")
        # Fallback: imagen de color sólido con gradiente
        img  = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 5, 30))
        draw = ImageDraw.Draw(img)
        for y in range(VIDEO_H):
            r = int(30 * (1 - y/VIDEO_H))
            b = int(80 * (1 - y/VIDEO_H))
            draw.line([(0,y),(VIDEO_W,y)], fill=(r, 0, b))
        img.save(str(output_path))
 
 
def generar_imagenes(prompts: list, fecha: str, indice: int) -> list:
    """Genera todas las imágenes IA para un vídeo."""
    imagenes = []
    for i, prompt in enumerate(prompts):
        img_path = OUTPUT_DIR / f"img_{fecha}_{indice}_{i}.jpg"
        generar_imagen_ia(prompt, img_path, i)
        imagenes.append(img_path)
        time.sleep(1)  # respetar rate limit de Pollinations
    return imagenes
 
 
# ══════════════════════════════════════════════
# PASO 3 — VOZ CON EDGE TTS
# ══════════════════════════════════════════════
 
async def generar_audio(texto: str, output_path: Path, voz: str):
    communicate = edge_tts.Communicate(texto, voz, rate="+8%")
    await communicate.save(str(output_path))
    log("  🔊", f"Audio: {output_path.name} ({output_path.stat().st_size // 1024} KB)")
 
 
# ══════════════════════════════════════════════
# PASO 4 — MINIATURA
# ══════════════════════════════════════════════
 
def crear_miniatura(titulo: str, primera_imagen: Path, output_path: Path):
    """Miniatura usando la primera imagen IA como fondo."""
    W, H = 1280, 720
 
    try:
        fondo = Image.open(str(primera_imagen)).resize((W, H))
        # Oscurecer para que el texto sea legible
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 140))
        fondo   = fondo.convert("RGBA")
        fondo   = Image.alpha_composite(fondo, overlay).convert("RGB")
    except Exception:
        fondo = Image.new("RGB", (W, H), (10, 5, 30))
 
    draw = ImageDraw.Draw(fondo)
 
    # Gradiente inferior
    for y in range(H//2, H):
        alpha = int(180 * ((y - H//2) / (H//2)))
        draw.line([(0,y),(W,y)], fill=(5, 0, 20))
 
    # Línea superior de color
    draw.rectangle([(0, 0), (W, 8)], fill=(180, 60, 255))
 
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_big  = ImageFont.truetype(font_path, 80)
        font_sub  = ImageFont.truetype(font_reg,  32)
    except Exception:
        font_big = font_sub = ImageFont.load_default()
 
    lineas  = textwrap.wrap(titulo, width=22)[:3]
    y_texto = H - 60 - (len(lineas) * 95)
    for linea in lineas:
        draw.text((W//2, y_texto), linea, font=font_big, fill="white",
                  anchor="mm", stroke_width=4, stroke_fill=(100, 0, 200))
        y_texto += 95
 
    draw.text((W//2, H - 40), "▶  Historia Narrada por IA",
              font=font_sub, fill=(200, 160, 255), anchor="mm")
 
    fondo.save(str(output_path), quality=95)
    log("  🖼", f"Miniatura: {output_path.name}")
 
 
# ══════════════════════════════════════════════
# PASO 5 — MONTAJE CON FFMPEG
# ══════════════════════════════════════════════
 
def imagen_a_clip(img_path: Path, duracion: float, clip_path: Path):
    """Convierte una imagen en un clip de vídeo con efecto Ken Burns (zoom suave)."""
    # Efecto Ken Burns: zoom lento del 100% al 108%
    zoom_filter = (
        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={int(duracion*FPS)}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
    )
    ffmpeg_run(
        "-loop", "1",
        "-i", str(img_path),
        "-vf", zoom_filter,
        "-t", str(duracion),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(clip_path)
    )
 
 
def montar_video(imagenes: list, audio_path: Path, output_path: Path):
    """Monta el vídeo: imágenes IA animadas + voz en off."""
    dur_total  = duracion_audio(audio_path)
    n_imagenes = len(imagenes)
    dur_cada   = dur_total / n_imagenes if n_imagenes > 0 else dur_total
 
    log("  🎞", f"Montando {n_imagenes} imágenes × {dur_cada:.1f}s = {dur_total:.1f}s")
 
    clips = []
    for i, img in enumerate(imagenes):
        clip_path = OUTPUT_DIR / f"clip_img_{output_path.stem}_{i}.mp4"
        try:
            imagen_a_clip(img, dur_cada, clip_path)
            clips.append(clip_path)
            log("  ✂️", f"Clip {i+1}/{n_imagenes} listo")
        except Exception as e:
            log("  ⚠️", f"Error clip {i+1}: {e}")
 
    if not clips:
        # Fondo negro de emergencia
        fondo = OUTPUT_DIR / f"fondo_{output_path.stem}.mp4"
        ffmpeg_run(
            "-f", "lavfi",
            "-i", f"color=c=black:size={VIDEO_W}x{VIDEO_H}:rate={FPS}",
            "-t", str(dur_total), "-c:v", "libx264", "-preset", "fast",
            str(fondo)
        )
        clips = [fondo]
 
    # Concatenar clips
    lista = OUTPUT_DIR / f"lista_{output_path.stem}.txt"
    lista.write_text("\n".join(f"file '{c.resolve()}'" for c in clips))
 
    concat = OUTPUT_DIR / f"concat_{output_path.stem}.mp4"
    ffmpeg_run("-f", "concat", "-safe", "0", "-i", str(lista),
               "-c", "copy", str(concat))
 
    # Unir con audio
    ffmpeg_run(
        "-i", str(concat),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(output_path)
    )
 
    log("  ✅", f"Vídeo listo: {output_path.name}")
 
    # Limpiar temporales
    for c in clips:
        c.unlink(missing_ok=True)
    concat.unlink(missing_ok=True)
    lista.unlink(missing_ok=True)
 
 
# ══════════════════════════════════════════════
# PASO 6 — SUBIDA A YOUTUBE
# ══════════════════════════════════════════════
 
def obtener_youtube():
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
    return build("youtube", "v3", credentials=creds, cache_discovery=False)
 
 
def subir_video(youtube, video_path: Path, thumb_path: Path, meta: dict) -> str:
    desc = (
        meta["descripcion"] + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 Suscríbete para historias nuevas cada día\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "#HistoriasIA #Narración #Misterio #Tecnología #CuriosidadesIA"
    )
    body = {
        "snippet": {
            "title":           meta["titulo"],
            "description":     desc,
            "tags":            meta["tags"] + ["historias IA", "narración", "misterio"],
            "categoryId":      "22",   # People & Blogs — mejor para storytelling
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }
    media   = MediaFileUpload(str(video_path), mimetype="video/mp4",
                              chunksize=10*1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
 
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log("  ↑", f"{int(status.progress()*100)}%")
 
    video_id = response["id"]
    log("  ✅", f"https://youtu.be/{video_id}")
 
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
        ).execute()
    except Exception as e:
        log("  ⚠️", f"Miniatura: {e}")
 
    return video_id
 
 
# ══════════════════════════════════════════════
# PRODUCIR UN VÍDEO COMPLETO
# ══════════════════════════════════════════════
 
async def producir_video(youtube, indice: int, fecha: str):
    genero = random.choice(GENEROS)
    voz    = random.choice(VOCES_ES)
    log("🎬", f"=== Vídeo {indice+1}/{VIDEOS_POR_LOTE} — {genero} ===")
 
    # 1. Guion
    meta = generar_guion(genero, indice)
 
    # 2. Audio
    audio_path = OUTPUT_DIR / f"audio_{fecha}_{indice}.mp3"
    await generar_audio(meta["guion"], audio_path, voz)
 
    # 3. Imágenes IA
    log("  🎨", "Generando imágenes con IA…")
    imagenes = generar_imagenes(meta["prompts_imagenes"], fecha, indice)
 
    # 4. Miniatura
    thumb_path = OUTPUT_DIR / f"thumb_{fecha}_{indice}.jpg"
    crear_miniatura(meta["titulo"], imagenes[0] if imagenes else Path("/dev/null"), thumb_path)
 
    # 5. Montar
    video_path = OUTPUT_DIR / f"video_{fecha}_{indice}.mp4"
    montar_video(imagenes, audio_path, video_path)
 
    # 6. Subir
    log("  📤", "Subiendo…")
    video_id = subir_video(youtube, video_path, thumb_path, meta)
 
    # Limpiar archivos grandes
    video_path.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)
    for img in imagenes:
        img.unlink(missing_ok=True)
 
    return {"titulo": meta["titulo"], "video_id": video_id,
            "url": f"https://youtu.be/{video_id}"}
 
 
# ══════════════════════════════════════════════
# PIPELINE PRINCIPAL — 5 VÍDEOS POR LOTE
# ══════════════════════════════════════════════
 
async def main():
    inicio = time.time()
    fecha  = datetime.now().strftime("%Y%m%d_%H%M")
    log("🚀", f"Lote iniciado — {fecha} — {VIDEOS_POR_LOTE} vídeos")
    print("═" * 55)
 
    youtube   = obtener_youtube()
    registro  = []
    exitosos  = 0
 
    for i in range(VIDEOS_POR_LOTE):
        try:
            resultado = await producir_video(youtube, i, fecha)
            registro.append({"fecha": fecha, **resultado})
            exitosos += 1
            print("─" * 55)
            # Pausa entre vídeos para no saturar APIs
            if i < VIDEOS_POR_LOTE - 1:
                log("⏳", "Esperando 30s antes del siguiente vídeo…")
                await asyncio.sleep(30)
        except Exception as e:
            log("❌", f"Vídeo {i+1} fallido: {e}")
            print("─" * 55)
 
    # Guardar registro
    with open(OUTPUT_DIR / "registro.jsonl", "a", encoding="utf-8") as f:
        for r in registro:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
 
    elapsed = int(time.time() - inicio)
    log("🎉", f"Lote completado: {exitosos}/{VIDEOS_POR_LOTE} vídeos en {elapsed//60}min {elapsed%60}s")
 
 
if __name__ == "__main__":
    asyncio.run(main())
