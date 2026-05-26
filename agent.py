
"""
╔══════════════════════════════════════════════════════════╗
║   AGENTE YOUTUBE — Estilo vacilón · Clips reales        ║
║   Groq · Pexels · Coqui TTS · ffmpeg · YouTube + Shorts ║
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
 
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
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
 
OUTPUT_DIR      = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
 
TTS_MODEL       = "tts_models/es/css10/vits"
VIDEO_W, VIDEO_H = 1920, 1080   # horizontal
SHORT_W, SHORT_H = 1080, 1920   # vertical Shorts
FPS              = 24
VIDEOS_POR_LOTE  = 5
 
TIPOS_VIDEO = [
    {
        "tipo": "entrevista_historica",
        "desc": "Un periodista de IA viaja al pasado y entrevista a un personaje histórico. Estilo vacilón, como si fuera un colega de bar.",
        "ejemplos": ["Julio César el día antes de morir", "un obrero que construyó las pirámides", "un marinero del Titanic horas antes", "Napoleón el día de Waterloo", "un habitante de Pompeya el día del volcán"]
    },
    {
        "tipo": "misterio_sin_resolver",
        "desc": "La IA investiga un misterio real con humor ácido y datos impactantes.",
        "ejemplos": ["quién fue Jack el Destripador", "qué pasó con la civilización Maya", "el triángulo de las Bermudas", "la ciudad perdida de Atlántida", "el misterio del vuelo MH370"]
    },
    {
        "tipo": "que_pasaria_si",
        "desc": "Escenario hipotético histórico o científico contado con mucho cachondeo.",
        "ejemplos": ["¿qué pasaría si Hitler hubiera ganado?", "¿y si Colón no llega a América?", "¿qué pasa si el sol desaparece mañana?", "¿y si los dinosaurios no se extinguen?"]
    },
    {
        "tipo": "dato_impactante_viral",
        "desc": "Datos reales absolutamente absurdos contados como si te los estuvieran revelando en secreto.",
        "ejemplos": ["datos del espacio que te harán sentir pequeño", "cosas que tu cuerpo hace sin que lo sepas", "secretos de la historia que te ocultaron", "datos de animales que parecen inventados"]
    },
    {
        "tipo": "curiosidad_cotidiana",
        "desc": "Explica algo cotidiano de forma absolutamente inesperada y cómica.",
        "ejemplos": ["por qué dormimos realmente", "el origen absurdo de palabras que usas", "por qué el tiempo pasa más rápido de adulto", "la ciencia de por qué la pizza sabe mejor tarde"]
    },
]
 
 
# ══════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════
 
def log(emoji, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {emoji}  {msg}", flush=True)
 
def reintentar(func, intentos=3, espera=8):
    for i in range(intentos):
        try:
            return func()
        except Exception as e:
            if i == intentos - 1:
                raise
            log("⚠️", f"Reintentando ({i+1}/{intentos}): {str(e)[:100]}")
            time.sleep(espera)
 
def ff(*args):
    r = subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {r.stderr[-400:]}")
 
def duracion(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 90.0
 
 
# ══════════════════════════════════════════════
# PASO 1 — GUION CON GROQ
# ══════════════════════════════════════════════
 
def generar_guion(tipo, indice):
    today   = datetime.now().strftime("%d de %B de %Y")
    ejemplo = random.choice(tipo["ejemplos"])
 
    prompt = f"""Fecha: {today}. Vídeo #{indice+1}.
Tipo: {tipo["tipo"]} — {tipo["desc"]}
Tema sugerido: {ejemplo}
 
El vídeo dura 55-60 segundos (para caber en Shorts). ESTILO:
- Tono vacilón, gracioso, como contárselo a tus colegas en un bar
- Expresiones españolas: 'tío', 'flipas', 'qué fuerte', 'me parto', 'macho', 'ostras', 'te lo juro'
- Primera frase: gancho absurdo o gracioso, imposible no seguir
- Datos REALES mezclados con comentarios sarcásticos y comparaciones absurdas
- Frases cortas, ritmo rápido, como stand-up comedy
- Remate final gracioso o dato tan absurdo que deje flipando
 
Responde SOLO JSON válido (sin markdown, sin texto extra):
{{
  "titulo": "Título YouTube máx 70 chars, con gancho fuerte, usa números o preguntas #Shorts",
  "titulo_largo": "Título para el vídeo largo (sin #Shorts, máx 70 chars)",
  "descripcion": "Descripción 180-220 chars con emojis, incita al clic",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8"],
  "escenas": [
    {{"descripcion": "escena 1 en español para buscar en Pexels", "keywords_pexels": "english keywords for pexels search"}},
    {{"descripcion": "escena 2", "keywords_pexels": "english keywords"}},
    {{"descripcion": "escena 3", "keywords_pexels": "english keywords"}},
    {{"descripcion": "escena 4", "keywords_pexels": "english keywords"}},
    {{"descripcion": "escena 5", "keywords_pexels": "english keywords"}},
    {{"descripcion": "escena 6", "keywords_pexels": "english keywords"}}
  ],
  "prompt_miniatura": "ultra realistic portrait or scene, [personaje/escena principal], dramatic cinematic lighting, intense expression, 4k, photorealistic",
  "texto_miniatura_linea1": "TEXTO GRANDE (máx 3 palabras)",
  "texto_miniatura_linea2": "texto segunda línea (máx 4 palabras)",
  "guion": "Guion completo voz en off. 130-150 palabras (para 55-60s). Vacilón, gracioso, español coloquial. Sin mencionar IA."
}}"""
 
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Guionista vacilón viral YouTube España. Responde SOLO JSON válido sin markdown."},
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
    log("📝", f"[{indice+1}/5] {meta['titulo_largo']}")
    return meta
 
 
# ══════════════════════════════════════════════
# PASO 2 — VOZ CON COQUI TTS
# ══════════════════════════════════════════════
 
async def generar_audio(texto, output_path):
    wav_path = output_path.with_suffix(".wav")
    r = subprocess.run(
        ["tts", "--text", texto, "--model_name", TTS_MODEL, "--out_path", str(wav_path)],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not wav_path.exists():
        raise RuntimeError(f"Coqui TTS: {r.stderr[-300:]}")
 
    # +8% velocidad para más energía
    ff("-i", str(wav_path), "-filter:a", "atempo=1.08",
       "-c:a", "libmp3lame", "-q:a", "2", str(output_path))
    wav_path.unlink(missing_ok=True)
    log("  🔊", f"Audio: {output_path.stat().st_size // 1024} KB")
 
 
# ══════════════════════════════════════════════
# PASO 3 — CLIPS DE PEXELS POR ESCENA
# ══════════════════════════════════════════════
 
def descargar_clip_escena(keywords: str, clip_path: Path) -> bool:
    """Descarga un clip de Pexels que coincida con la escena."""
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        url  = (f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(keywords)}"
                f"&per_page=10&orientation=landscape&size=medium")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return False
        random.shuffle(videos)
 
        for v in videos[:5]:
            archivos = sorted(v.get("video_files", []),
                              key=lambda x: x.get("width", 0), reverse=True)
            candidato = next(
                (f for f in archivos if 1280 <= f.get("width", 0) <= 1920),
                archivos[0] if archivos else None
            )
            if not candidato:
                continue
            datos = requests.get(candidato["link"], timeout=60).content
            if len(datos) < 50000:
                continue
            clip_path.write_bytes(datos)
            log("  📥", f"Clip '{keywords[:30]}' ({len(datos)//1024} KB)")
            return True
    except Exception as e:
        log("  ⚠️", f"Pexels error ({keywords[:30]}): {e}")
    return False
 
 
def obtener_clips_escenas(escenas: list, fecha: str, indice: int) -> list:
    """Descarga un clip por escena del guion."""
    clips = []
    for i, escena in enumerate(escenas):
        clip_path = OUTPUT_DIR / f"clip_{fecha}_{indice}_{i}.mp4"
        ok = descargar_clip_escena(escena["keywords_pexels"], clip_path)
        if not ok:
            # Fallback: buscar con keywords más genéricas
            ok = descargar_clip_escena("cinematic dramatic scene", clip_path)
        if ok:
            clips.append(clip_path)
        time.sleep(0.5)
    return clips
 
 
# ══════════════════════════════════════════════
# PASO 4 — MINIATURA PROFESIONAL (Pollinations)
# ══════════════════════════════════════════════
 
def generar_imagen_miniatura(prompt: str, output_path: Path):
    prompt_enc = urllib.parse.quote(prompt[:500])
    seed       = random.randint(1, 999999)
    url        = (f"https://image.pollinations.ai/prompt/{prompt_enc}"
                  f"?width=1280&height=720&nologo=true&seed={seed}&model=flux")
    def _dl():
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        if len(resp.content) < 5000:
            raise ValueError("Imagen pequeña")
        output_path.write_bytes(resp.content)
    try:
        reintentar(_dl, intentos=3, espera=6)
    except Exception:
        img  = Image.new("RGB", (1280, 720), (15, 10, 35))
        draw = ImageDraw.Draw(img)
        for y in range(720):
            draw.line([(0,y),(1280,y)], fill=(int(40*(1-y/720)), 0, int(100*(1-y/720))))
        img.save(str(output_path))
 
 
def crear_miniatura_pro(meta, fecha, indice, output_path):
    W, H = 1280, 720
    img_path = OUTPUT_DIR / f"thumb_bg_{fecha}_{indice}.jpg"
    generar_imagen_miniatura(meta["prompt_miniatura"], img_path)
 
    try:
        fondo = Image.open(str(img_path)).convert("RGB").resize((W, H))
        fondo = ImageEnhance.Contrast(fondo).enhance(1.25)
        fondo = ImageEnhance.Color(fondo).enhance(1.35)
    except Exception:
        fondo = Image.new("RGB", (W, H), (15, 10, 35))
 
    draw = ImageDraw.Draw(fondo)
 
    # Gradiente oscuro inferior
    for y in range(H // 2, H):
        ratio = (y - H // 2) / (H // 2)
        r, g, b = fondo.getpixel((W // 2, y))
        nr = max(0, int(r * (1 - ratio * 0.75)))
        ng = max(0, int(g * (1 - ratio * 0.75)))
        nb = max(0, int(b * (1 - ratio * 0.75)))
        draw.line([(0, y), (W, y)], fill=(nr, ng, nb))
 
    draw.rectangle([(0, 0), (W, 10)], fill=(255, 40, 40))
 
    try:
        fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        fr = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f1 = ImageFont.truetype(fb, 115)
        f2 = ImageFont.truetype(fb, 70)
        f3 = ImageFont.truetype(fr, 34)
    except Exception:
        f1 = f2 = f3 = ImageFont.load_default()
 
    l1 = meta.get("texto_miniatura_linea1", "").upper()
    l2 = meta.get("texto_miniatura_linea2", "")
 
    # Texto línea 1 — amarillo con borde negro
    for dx, dy in [(-5,-5),(5,-5),(-5,5),(5,5),(0,-6),(0,6),(-6,0),(6,0)]:
        draw.text((W//2+dx, H-235+dy), l1, font=f1, fill=(0,0,0), anchor="mm")
    draw.text((W//2, H-235), l1, font=f1, fill=(255, 225, 0), anchor="mm")
 
    # Texto línea 2 — blanco con borde
    for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3)]:
        draw.text((W//2+dx, H-115+dy), l2, font=f2, fill=(0,0,0), anchor="mm")
    draw.text((W//2, H-115), l2, font=f2, fill=(255,255,255), anchor="mm")
 
    # Badge
    draw.rounded_rectangle([(25,20),(250,72)], radius=12, fill=(210,30,30))
    draw.text((137,46), "▶ HISTORIA IA", font=f3, fill="white", anchor="mm")
 
    fondo.save(str(output_path), quality=97)
    img_path.unlink(missing_ok=True)
    log("  🖼", "Miniatura lista")
 
 
# ══════════════════════════════════════════════
# PASO 5 — MONTAJE HORIZONTAL (1920x1080)
# ══════════════════════════════════════════════
 
# Efectos de movimiento disponibles
EFECTOS = [
    # zoom in lento
    "scale=8000:-1,zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={W}x{H}:fps={fps}",
    # zoom out
    "scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.05,max(zoom-0.0005,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={W}x{H}:fps={fps}",
    # paneo izquierda a derecha
    "scale=8000:-1,zoompan=z='1.04':x='iw*{t}/8000-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={W}x{H}:fps={fps}",
    # paneo arriba a abajo
    "scale=8000:-1,zoompan=z='1.04':x='iw/2-(iw/zoom/2)':y='ih*{t}/8000-(ih/zoom/2)':d={d}:s={W}x{H}:fps={fps}",
]
 
def clip_con_efecto(clip_path: Path, dur: float, out_path: Path, w: int, h: int):
    """Recorta un fragmento del clip y le aplica efecto de movimiento."""
    dur_clip = duracion(clip_path)
    inicio   = random.uniform(0, max(0, dur_clip - dur - 1))
    n_frames = int(dur * FPS)
 
    efecto = random.choice(EFECTOS).format(d=n_frames, W=w, H=h, fps=FPS, t="n")
 
    # Recortar + escalar grande + efecto zoompan
    vf = (f"trim=start={inicio:.2f}:duration={dur:.2f},setpts=PTS-STARTPTS,"
          f"scale={w*4}:{h*4}:force_original_aspect_ratio=increase,"
          f"crop={w*4}:{h*4},"
          f"zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d={n_frames}:s={w}x{h}:fps={FPS}")
 
    ff("-i", str(clip_path), "-vf", vf,
       "-t", str(dur), "-c:v", "libx264", "-preset", "fast",
       "-crf", "22", "-pix_fmt", "yuv420p", "-an", str(out_path))
 
 
def montar_horizontal(clips: list, audio_path: Path, output_path: Path):
    """Monta el vídeo horizontal 1920x1080."""
    dur_total = duracion(audio_path)
    n         = len(clips)
    if n == 0:
        ff("-f", "lavfi", "-i", f"color=c=black:size={VIDEO_W}x{VIDEO_H}:rate={FPS}",
           "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
           "-t", str(dur_total), "-c:v", "libx264", "-c:a", "aac", str(output_path))
        return
 
    dur_cada = dur_total / n
    frags    = []
 
    for i, cp in enumerate(clips):
        fp = OUTPUT_DIR / f"frag_h_{output_path.stem}_{i}.mp4"
        try:
            clip_con_efecto(cp, dur_cada, fp, VIDEO_W, VIDEO_H)
            frags.append(fp)
        except Exception as e:
            log("  ⚠️", f"Frag H {i}: {e}")
 
    if not frags:
        ff("-f", "lavfi", "-i", f"color=c=black:size={VIDEO_W}x{VIDEO_H}:rate={FPS}",
           "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
           "-t", str(dur_total), "-c:v", "libx264", "-c:a", "aac", str(output_path))
        return
 
    lista = OUTPUT_DIR / f"lista_h_{output_path.stem}.txt"
    lista.write_text("\n".join(f"file '{f.resolve()}'" for f in frags))
    concat = OUTPUT_DIR / f"concat_h_{output_path.stem}.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(concat))
    ff("-i", str(concat), "-i", str(audio_path),
       "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
       "-shortest", str(output_path))
 
    for f in frags: f.unlink(missing_ok=True)
    concat.unlink(missing_ok=True)
    lista.unlink(missing_ok=True)
    log("  ✅", f"Horizontal: {output_path.name}")
 
 
def montar_shorts(clips: list, audio_path: Path, output_path: Path):
    """Monta la versión vertical 1080x1920 para Shorts."""
    dur_total = duracion(audio_path)
    # Shorts: máx 59 segundos
    dur_short = min(dur_total, 58.0)
    n         = len(clips)
    if n == 0:
        ff("-f", "lavfi", "-i", f"color=c=black:size={SHORT_W}x{SHORT_H}:rate={FPS}",
           "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
           "-t", str(dur_short), "-c:v", "libx264", "-c:a", "aac", str(output_path))
        return
 
    dur_cada = dur_short / n
    frags    = []
 
    for i, cp in enumerate(clips):
        fp = OUTPUT_DIR / f"frag_s_{output_path.stem}_{i}.mp4"
        try:
            clip_con_efecto(cp, dur_cada, fp, SHORT_W, SHORT_H)
            frags.append(fp)
        except Exception as e:
            log("  ⚠️", f"Frag S {i}: {e}")
 
    if not frags:
        ff("-f", "lavfi", "-i", f"color=c=black:size={SHORT_W}x{SHORT_H}:rate={FPS}",
           "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
           "-t", str(dur_short), "-c:v", "libx264", "-c:a", "aac", str(output_path))
        return
 
    lista = OUTPUT_DIR / f"lista_s_{output_path.stem}.txt"
    lista.write_text("\n".join(f"file '{f.resolve()}'" for f in frags))
    concat = OUTPUT_DIR / f"concat_s_{output_path.stem}.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(concat))
 
    # Recortar audio a duración del short
    audio_short = OUTPUT_DIR / f"audio_short_{output_path.stem}.mp3"
    ff("-i", str(audio_path), "-t", str(dur_short), "-c", "copy", str(audio_short))
 
    ff("-i", str(concat), "-i", str(audio_short),
       "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
       "-shortest", str(output_path))
 
    for f in frags: f.unlink(missing_ok=True)
    concat.unlink(missing_ok=True)
    lista.unlink(missing_ok=True)
    audio_short.unlink(missing_ok=True)
    log("  ✅", f"Shorts: {output_path.name}")
 
 
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
 
 
def subir(youtube, video_path, thumb_path, titulo, meta, es_short=False):
    desc = (
        meta["descripcion"] + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 Suscríbete — historia nueva cada día\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + ("#Shorts #HistoriaIA #Viral" if es_short else "#HistoriaIA #Viral #Curiosidades")
    )
    body = {
        "snippet": {
            "title":           titulo,
            "description":     desc,
            "tags":            meta["tags"] + (["Shorts"] if es_short else []) + ["historias IA", "viral"],
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
    vid = response["id"]
    log("  ✅", f"{'Short' if es_short else 'Vídeo'}: https://youtu.be/{vid}")
 
    if thumb_path and thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=vid,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
            ).execute()
        except Exception as e:
            log("  ⚠️", f"Miniatura: {e}")
    return vid
 
 
# ══════════════════════════════════════════════
# PIPELINE — UN VÍDEO COMPLETO
# ══════════════════════════════════════════════
 
async def producir_video(youtube, indice, fecha):
    tipo = random.choice(TIPOS_VIDEO)
    log("🎬", f"=== Vídeo {indice+1}/{VIDEOS_POR_LOTE} — {tipo['tipo']} ===")
 
    # 1. Guion
    meta = generar_guion(tipo, indice)
 
    # 2. Audio
    audio_path = OUTPUT_DIR / f"audio_{fecha}_{indice}.mp3"
    await generar_audio(meta["guion"], audio_path)
 
    # 3. Clips por escena
    log("  🎬", f"Descargando {len(meta['escenas'])} clips de Pexels…")
    clips = obtener_clips_escenas(meta["escenas"], fecha, indice)
 
    # 4. Miniatura
    thumb_path = OUTPUT_DIR / f"thumb_{fecha}_{indice}.jpg"
    crear_miniatura_pro(meta, fecha, indice, thumb_path)
 
    # 5a. Montar vídeo horizontal
    video_h = OUTPUT_DIR / f"video_h_{fecha}_{indice}.mp4"
    log("  🎞", "Montando horizontal…")
    montar_horizontal(clips, audio_path, video_h)
 
    # 5b. Montar Shorts vertical
    video_s = OUTPUT_DIR / f"video_s_{fecha}_{indice}.mp4"
    log("  📱", "Montando Shorts…")
    montar_shorts(clips, audio_path, video_s)
 
    # 6. Subir ambos
    log("  📤", "Subiendo vídeo normal…")
    vid_normal = subir(youtube, video_h, thumb_path, meta["titulo_largo"], meta, es_short=False)
 
    log("  📤", "Subiendo Short…")
    vid_short  = subir(youtube, video_s, thumb_path, meta["titulo"], meta, es_short=True)
 
    # Limpiar
    for f in [video_h, video_s, audio_path, thumb_path] + clips:
        Path(f).unlink(missing_ok=True)
 
    return {
        "titulo": meta["titulo_largo"],
        "video_id": vid_normal, "short_id": vid_short,
        "url": f"https://youtu.be/{vid_normal}",
        "short_url": f"https://youtu.be/{vid_short}",
    }
 
 
# ══════════════════════════════════════════════
# MAIN — 5 VÍDEOS POR LOTE
# ══════════════════════════════════════════════
 
async def main():
    inicio = time.time()
    fecha  = datetime.now().strftime("%Y%m%d_%H%M")
    log("🚀", f"Lote — {fecha} — {VIDEOS_POR_LOTE} vídeos + {VIDEOS_POR_LOTE} Shorts")
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
                log("⏳", "Pausa 20s…")
                await asyncio.sleep(20)
        except Exception as e:
            log("❌", f"Vídeo {i+1} fallido: {e}")
            print("─" * 60)
 
    with open(OUTPUT_DIR / "registro.jsonl", "a", encoding="utf-8") as f:
        for r in registro:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
 
    elapsed = int(time.time() - inicio)
    log("🎉", f"{exitosos}/{VIDEOS_POR_LOTE} lote en {elapsed//60}m {elapsed%60}s")
 
 
if __name__ == "__main__":
    asyncio.run(main())
