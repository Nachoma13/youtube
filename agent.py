"""
╔══════════════════════════════════════════════════════════╗
║   AGENTE YOUTUBE — Estilo "Oddly Ordinary AI"           ║
║   Entrevistas históricas · Humor · Imágenes IA          ║
║   Groq · Pollinations · Edge TTS · ffmpeg · YouTube     ║
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
from io import BytesIO
 
import subprocess as _sp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
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
 
VIDEO_W         = 1920
VIDEO_H         = 1080
FPS             = 24
VIDEOS_POR_LOTE = 5
 
# Voces disponibles en Edge TTS
# Coqui TTS — voz española masculina natural
TTS_MODEL = "tts_models/es/css10/vits"
 
# Tipos de vídeos estilo Oddly Ordinary AI
TIPOS_VIDEO = [
    {
        "tipo": "entrevista_historica",
        "descripcion": "Un periodista de IA viaja al pasado y entrevista a un personaje histórico famoso sobre un momento clave de la historia. Tono: mitad serio, mitad humorístico. El personaje habla en primera persona con expresiones de la época.",
        "ejemplos": ["Julio César el día antes de ser asesinado", "un obrero que construyó las pirámides", "un marinero del Titanic horas antes del hundimiento", "un soldado en la batalla de Waterloo", "un habitante de Pompeya el día del volcán"]
    },
    {
        "tipo": "misterio_sin_resolver",
        "descripcion": "La IA investiga uno de los grandes misterios de la historia o el universo. Tono periodístico + dramático. Revela datos reales impactantes que la gente no conoce.",
        "ejemplos": ["quién fue Jack el Destripador realmente", "qué pasó con la civilización Maya", "el triángulo de las Bermudas explicado con ciencia real", "el misterio del número 42 en el universo", "la ciudad perdida de Atlántida"]
    },
    {
        "tipo": "que_pasaria_si",
        "descripcion": "La IA explora un escenario hipotético histórico o científico. '¿Qué habría pasado si...?' con rigor histórico y humor. Muy visual y narrativo.",
        "ejemplos": ["¿qué pasaría si Hitler hubiera ganado la Segunda Guerra Mundial?", "¿y si Colón no hubiera llegado a América?", "¿qué pasaría si el sol desapareciera mañana?", "¿y si los dinosaurios no se hubieran extinguido?"]
    },
    {
        "tipo": "dato_impactante_viral",
        "descripcion": "La IA revela datos reales absolutamente impactantes que nadie conoce. Tono de descubrimiento y asombro. Cada dato es más sorprendente que el anterior.",
        "ejemplos": ["datos sobre el espacio que te harán sentir pequeño", "cosas que tu cuerpo hace sin que lo sepas", "secretos de la historia que te ocultaron en el colegio", "datos de animales que parecen inventados pero son reales"]
    },
    {
        "tipo": "curiosidad_cotidiana_ia",
        "descripcion": "La IA usa humor e inteligencia artificial para explicar algo de la vida cotidiana de forma absolutamente inesperada y viral. Estilo cómico pero educativo.",
        "ejemplos": ["por qué dormimos realmente según la ciencia", "el origen absurdo de las palabras que usas cada día", "por qué el tiempo pasa más rápido cuando eres adulto", "la ciencia detrás de por qué la pizza sabe mejor a las 2am"]
    },
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
            log("⚠️", f"Reintentando ({i+1}/{intentos}): {str(e)[:100]}")
            time.sleep(espera)
 
 
def ffmpeg_run(*args):
    cmd    = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg: {result.stderr[-500:]}")
 
 
def duracion_audio(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except Exception:
        return 90.0
 
 
# ══════════════════════════════════════════════
# PASO 1 — GUION CON GROQ
# ══════════════════════════════════════════════
 
def generar_guion(tipo_video: dict, indice: int) -> dict:
    today   = datetime.now().strftime("%d de %B de %Y")
    ejemplo = random.choice(tipo_video["ejemplos"])
 
    prompt = f"""Fecha: {today}. Eres el guionista del canal de YouTube más viral de España en 2025.
Tu estilo: como "Oddly Ordinary AI" — mezcla de humor, drama, datos reales y narración adictiva.
 
Tipo de vídeo: {tipo_video["tipo"]}
Descripción del estilo: {tipo_video["descripcion"]}
Tema sugerido (puedes mejorarlo): {ejemplo}
 
El vídeo dura 90-120 segundos. REGLAS DE ESTILO:
- Primera frase: un gancho absurdo o gracioso que enganche al instante
- Tono: como si lo contaras vacilando a tus colegas en un bar, con cachondeo
- Usa expresiones coloquiales españolas: 'tío', 'flipas', 'qué fuerte', 'me parto', 'macho', 'ostras', 'menuda historia', 'te lo juro'
- Mezcla datos reales con comentarios sarcásticos y comparaciones absurdas con la vida de hoy
- Ríete de los personajes o situaciones con respeto pero con humor
- Frases cortas, ritmo rápido, como stand-up comedy
- Termina con un remate gracioso o un dato tan absurdo que deje al espectador flipando
 
Responde SOLO con este JSON válido (sin markdown, sin texto extra):
{{
  "titulo": "Título YouTube máx 70 chars. Usa mayúsculas, números o preguntas. Que genere curiosidad extrema",
  "descripcion": "Descripción 180-220 chars con emojis. Debe incitar al clic",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8"],
  "prompts_imagenes": [
    "ultra realistic cinematic still, [escena específica del vídeo 1], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 2], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 3], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 4], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 5], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 6], dramatic lighting, 8k, film grain, photorealistic",
    "ultra realistic cinematic still, [escena específica del vídeo 7], dramatic lighting, 8k, film grain, photorealistic"
  ],
  "prompt_miniatura": "ultra realistic portrait, [personaje o escena principal del vídeo], dramatic cinematic lighting, intense expression, 4k, photorealistic, high detail face",
  "texto_miniatura_linea1": "TEXTO GRANDE LÍNEA 1 (máx 3 palabras, impacto máximo)",
  "texto_miniatura_linea2": "texto segunda línea (máx 4 palabras, complementa la 1)",
  "guion": "Guion completo voz en off. 230-280 palabras. Empieza con gancho brutal. Ritmo rápido, frases cortas. Datos reales. Humor sutil. Sin mencionar que es IA."
}}"""
 
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model":       "llama-3.3-70b-versatile",
        "messages":    [
            {"role": "system", "content": """Eres el guionista más gracioso y vacilón de YouTube en España.
Tu estilo: humor ácido, expresiones coloquiales españolas ('tío', 'macho', 'flipas', 'me parto', 'qué fuerte', 'ostias', 'menuda historia'),
reírte de la situación, comentarios sarcásticos, comparaciones absurdas con la vida moderna.
Como si lo estuvieras contando a tus colegas en un bar, no en una clase.
Datos reales pero contados con cachondeo. Nunca aburrido. Responde SOLO JSON válido sin markdown ni texto extra."""},
            {"role": "user",   "content": prompt}
        ],
        "temperature": 0.95,
        "max_tokens":  2000,
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
# PASO 2 — VOZ CON EDGE TTS
# ══════════════════════════════════════════════
 
async def generar_audio(texto: str, output_path: Path, voz: str = None):
    """Genera audio con Coqui TTS — voz española masculina natural."""
    # Guardar texto en archivo temporal (evita problemas con caracteres especiales)
    txt_path = output_path.with_suffix(".txt")
    txt_path.write_text(texto, encoding="utf-8")
 
    wav_path = output_path.with_suffix(".wav")
 
    result = _sp.run(
        ["tts", "--text", texto,
         "--model_name", TTS_MODEL,
         "--out_path", str(wav_path)],
        capture_output=True, text=True
    )
 
    if result.returncode != 0 or not wav_path.exists():
        raise RuntimeError(f"Coqui TTS error: {result.stderr[-300:]}")
 
    # Convertir WAV a MP3 y subir velocidad ligeramente (+8%) para tono dinámico
    ffmpeg_run(
        "-i", str(wav_path),
        "-filter:a", "atempo=1.08",   # +8% velocidad, más energía
        "-c:a", "libmp3lame", "-q:a", "2",
        str(output_path)
    )
 
    wav_path.unlink(missing_ok=True)
    txt_path.unlink(missing_ok=True)
    log("  🔊", f"Audio Coqui: {output_path.stat().st_size // 1024} KB")
 
 
# ══════════════════════════════════════════════
# PASO 3 — IMÁGENES IA CON POLLINATIONS
# ══════════════════════════════════════════════
 
def generar_imagen(prompt: str, output_path: Path, ancho: int, alto: int):
    """Genera imagen con Pollinations.ai (gratis, sin límites)."""
    prompt_enc = urllib.parse.quote(prompt[:500])
    seed       = random.randint(1, 999999)
    url        = (f"https://image.pollinations.ai/prompt/{prompt_enc}"
                  f"?width={ancho}&height={alto}&nologo=true&seed={seed}&model=flux")
 
    def _descargar():
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        if len(resp.content) < 5000:
            raise ValueError("Imagen demasiado pequeña")
        output_path.write_bytes(resp.content)
 
    try:
        reintentar(_descargar, intentos=3, espera=6)
        log("  🎨", f"Imagen OK ({output_path.stat().st_size // 1024} KB)")
    except Exception as e:
        log("  ⚠️", f"Imagen fallida: {e} — usando fondo")
        img  = Image.new("RGB", (ancho, alto), (15, 10, 35))
        draw = ImageDraw.Draw(img)
        for y in range(alto):
            r = int(40 * (1 - y/alto))
            b = int(100 * (1 - y/alto))
            draw.line([(0, y), (ancho, y)], fill=(r, 0, b))
        img.save(str(output_path))
 
 
def generar_imagenes_video(prompts: list, fecha: str, indice: int) -> list:
    imagenes = []
    for i, prompt in enumerate(prompts):
        p = OUTPUT_DIR / f"img_{fecha}_{indice}_{i}.jpg"
        generar_imagen(prompt, p, VIDEO_W, VIDEO_H)
        imagenes.append(p)
        time.sleep(2)
    return imagenes
 
 
# ══════════════════════════════════════════════
# PASO 4 — MINIATURA PROFESIONAL
# ══════════════════════════════════════════════
 
def crear_miniatura_pro(meta: dict, fecha: str, indice: int, output_path: Path):
    """
    Miniatura estilo canal viral:
    - Imagen IA del personaje/escena como fondo
    - Texto grande y llamativo con sombra y borde
    - Franja de color inferior
    - Badge o etiqueta llamativa
    """
    W, H = 1280, 720
 
    # Generar imagen específica para miniatura (más cuadrada, cara grande)
    thumb_img_path = OUTPUT_DIR / f"thumb_img_{fecha}_{indice}.jpg"
    generar_imagen(meta["prompt_miniatura"], thumb_img_path, W, H)
 
    try:
        fondo = Image.open(str(thumb_img_path)).convert("RGB").resize((W, H))
    except Exception:
        fondo = Image.new("RGB", (W, H), (15, 10, 35))
 
    # Aumentar contraste y saturación para que sea más llamativa
    fondo = ImageEnhance.Contrast(fondo).enhance(1.2)
    fondo = ImageEnhance.Color(fondo).enhance(1.3)
 
    draw = ImageDraw.Draw(fondo)
 
    # ── Gradiente oscuro en la mitad inferior para que el texto sea legible
    for y in range(H // 2, H):
        alpha = int(210 * ((y - H // 2) / (H // 2)))
        # Overlay oscuro progresivo
        px = fondo.getpixel((W // 2, y))
        r  = max(0, px[0] - alpha // 3)
        g  = max(0, px[1] - alpha // 3)
        b  = max(0, px[2] - alpha // 3)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
 
    # ── Franja superior con color de marca
    draw.rectangle([(0, 0), (W, 10)], fill=(255, 50, 50))
 
    # ── Cargar fuentes
    try:
        font_bold  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg   = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f_grande   = ImageFont.truetype(font_bold, 110)
        f_mediana  = ImageFont.truetype(font_bold, 68)
        f_pequeña  = ImageFont.truetype(font_reg,  36)
    except Exception:
        f_grande = f_mediana = f_pequeña = ImageFont.load_default()
 
    linea1 = meta.get("texto_miniatura_linea1", "").upper()
    linea2 = meta.get("texto_miniatura_linea2", "")
 
    # ── Línea 1 grande (borde negro grueso + texto blanco/amarillo)
    y1 = H - 230
    for dx, dy in [(-4,-4),(4,-4),(-4,4),(4,4),(0,-5),(0,5),(-5,0),(5,0)]:
        draw.text((W//2 + dx, y1 + dy), linea1, font=f_grande,
                  fill=(0, 0, 0), anchor="mm")
    draw.text((W//2, y1), linea1, font=f_grande, fill=(255, 230, 0), anchor="mm")
 
    # ── Línea 2 mediana (blanca con sombra)
    y2 = H - 115
    for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3)]:
        draw.text((W//2 + dx, y2 + dy), linea2, font=f_mediana,
                  fill=(0, 0, 0), anchor="mm")
    draw.text((W//2, y2), linea2, font=f_mediana, fill=(255, 255, 255), anchor="mm")
 
    # ── Badge rojo superior izquierda "🔴 EN VÍDEO"
    badge_x, badge_y = 30, 25
    draw.rounded_rectangle([(badge_x, badge_y), (badge_x+220, badge_y+55)],
                            radius=12, fill=(220, 30, 30))
    draw.text((badge_x + 110, badge_y + 27), "▶ HISTORIA IA",
              font=f_pequeña, fill="white", anchor="mm")
 
    fondo.save(str(output_path), quality=97)
    log("  🖼", f"Miniatura pro lista: {output_path.name}")
 
    # Limpiar imagen temporal de miniatura
    thumb_img_path.unlink(missing_ok=True)
 
 
# ══════════════════════════════════════════════
# PASO 5 — MONTAJE CON FFMPEG (Ken Burns)
# ══════════════════════════════════════════════
 
def imagen_a_clip(img_path: Path, duracion: float, clip_path: Path):
    """Convierte imagen en clip con efecto Ken Burns (zoom + paneo suave)."""
    n_frames  = int(duracion * FPS)
    # Alternar entre zoom in y zoom out + distintos puntos de inicio
    direccion = random.choice([
        "z='min(zoom+0.0006,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",          # zoom in centro
        "z='if(lte(zoom,1.0),1.06,max(zoom-0.0006,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",  # zoom out
        "z='min(zoom+0.0006,1.06)':x='0':y='ih/2-(ih/zoom/2)'",                           # zoom + paneo derecha
        "z='min(zoom+0.0006,1.06)':x='iw-(iw/zoom)':y='ih/2-(ih/zoom/2)'",               # zoom + paneo izquierda
    ])
    zoom_filter = (
        f"zoompan=z='{direccion.split(chr(39))[1]}':"
        f"x='{direccion.split(chr(39))[3]}':"
        f"y='{direccion.split(chr(39))[5]}':"
        f"d={n_frames}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
    )
    # Forma simplificada y robusta
    zoom_filter = (
        f"scale=8000:-1,zoompan=z='min(zoom+0.0005,1.05)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={n_frames}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
    )
    ffmpeg_run(
        "-loop", "1",
        "-i", str(img_path),
        "-vf", zoom_filter,
        "-t", str(duracion),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(clip_path)
    )
 
 
def montar_video(imagenes: list, audio_path: Path, output_path: Path):
    dur_total  = duracion_audio(audio_path)
    n          = len(imagenes)
    dur_cada   = dur_total / n if n > 0 else dur_total
 
    log("  🎞", f"Montando {n} imágenes × {dur_cada:.1f}s")
 
    clips = []
    for i, img in enumerate(imagenes):
        clip_path = OUTPUT_DIR / f"clip_{output_path.stem}_{i}.mp4"
        try:
            imagen_a_clip(img, dur_cada, clip_path)
            clips.append(clip_path)
        except Exception as e:
            log("  ⚠️", f"Clip {i+1} error: {e}")
 
    if not clips:
        fondo = OUTPUT_DIR / f"fondo_{output_path.stem}.mp4"
        ffmpeg_run("-f", "lavfi",
                   "-i", f"color=c=black:size={VIDEO_W}x{VIDEO_H}:rate={FPS}",
                   "-t", str(dur_total), "-c:v", "libx264", str(fondo))
        clips = [fondo]
 
    lista = OUTPUT_DIR / f"lista_{output_path.stem}.txt"
    lista.write_text("\n".join(f"file '{c.resolve()}'" for c in clips))
 
    concat = OUTPUT_DIR / f"concat_{output_path.stem}.mp4"
    ffmpeg_run("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(concat))
 
    ffmpeg_run(
        "-i", str(concat),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path)
    )
 
    log("  ✅", f"Vídeo: {output_path.name}")
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
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 Suscríbete — historia nueva cada día\n"
        "📩 ¿Qué historia quieres que contemos mañana?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "#HistoriaIA #CuriosidadesIA #Misterio #Historia #Viral"
    )
    body = {
        "snippet": {
            "title":           meta["titulo"],
            "description":     desc,
            "tags":            meta["tags"] + ["historias IA", "narración", "viral", "curiosidades"],
            "categoryId":      "22",
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
        log("  🖼", "Miniatura subida")
    except Exception as e:
        log("  ⚠️", f"Miniatura: {e}")
 
    return video_id
 
 
# ══════════════════════════════════════════════
# PRODUCIR UN VÍDEO COMPLETO
# ══════════════════════════════════════════════
 
async def producir_video(youtube, indice: int, fecha: str):
    tipo = random.choice(TIPOS_VIDEO)
 
    log("🎬", f"=== Vídeo {indice+1}/{VIDEOS_POR_LOTE} — {tipo['tipo']} ===")
 
    # 1. Guion
    meta = generar_guion(tipo, indice)
 
    # 2. Audio
    audio_path = OUTPUT_DIR / f"audio_{fecha}_{indice}.mp3"
    await generar_audio(meta["guion"], audio_path)
 
    # 3. Imágenes IA para el vídeo
    log("  🎨", f"Generando {len(meta['prompts_imagenes'])} imágenes IA…")
    imagenes = generar_imagenes_video(meta["prompts_imagenes"], fecha, indice)
 
    # 4. Miniatura profesional (imagen IA específica)
    thumb_path = OUTPUT_DIR / f"thumb_{fecha}_{indice}.jpg"
    crear_miniatura_pro(meta, fecha, indice, thumb_path)
 
    # 5. Montar vídeo
    video_path = OUTPUT_DIR / f"video_{fecha}_{indice}.mp4"
    montar_video(imagenes, audio_path, video_path)
 
    # 6. Subir
    log("  📤", "Subiendo a YouTube…")
    video_id = subir_video(youtube, video_path, thumb_path, meta)
 
    # Limpiar archivos grandes
    video_path.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)
    thumb_path.unlink(missing_ok=True)
    for img in imagenes:
        img.unlink(missing_ok=True)
 
    return {"titulo": meta["titulo"], "video_id": video_id,
            "url": f"https://youtu.be/{video_id}"}
 
 
# ══════════════════════════════════════════════
# PIPELINE — 5 VÍDEOS POR LOTE
# ══════════════════════════════════════════════
 
async def main():
    inicio = time.time()
    fecha  = datetime.now().strftime("%Y%m%d_%H%M")
    log("🚀", f"Lote iniciado — {fecha} — {VIDEOS_POR_LOTE} vídeos")
    print("═" * 60)
 
    youtube  = obtener_youtube()
    registro = []
    exitosos = 0
 
    for i in range(VIDEOS_POR_LOTE):
        try:
            r = await producir_video(youtube, i, fecha)
            registro.append({"fecha": fecha, **r})
            exitosos += 1
            print("─" * 60)
            if i < VIDEOS_POR_LOTE - 1:
                log("⏳", "Pausa 20s antes del siguiente…")
                await asyncio.sleep(20)
        except Exception as e:
            log("❌", f"Vídeo {i+1} fallido: {e}")
            print("─" * 60)
 
    with open(OUTPUT_DIR / "registro.jsonl", "a", encoding="utf-8") as f:
        for r in registro:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
 
    elapsed = int(time.time() - inicio)
    log("🎉", f"Lote: {exitosos}/{VIDEOS_POR_LOTE} vídeos en {elapsed//60}min {elapsed%60}s")
 
 
if __name__ == "__main__":
    asyncio.run(main())
