#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Historias Anime V2.0
Publica 10-15 historias diarias automáticamente desde posts antiguos de Facebook
Intervalo configurable (default 96 min = 15 historias/día)
"""

import requests
import json
import os
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Cargar variables de entorno
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DESDE .env
# =============================================================================

FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
IG_ACCOUNT_ID = os.getenv('IG_ACCOUNT_ID')

# Configuración de historias
INTERVALO_MINUTOS = int(os.getenv('INTERVALO_MINUTOS', '96'))
MAX_HISTORIAS_DIA = int(os.getenv('MAX_HISTORIAS_DIA', '15'))
DIAS_ATRAS = int(os.getenv('DIAS_ATRAS', '30'))
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAS_PATH = os.path.join(BASE_DIR, 'data', 'historial_historias.json')

# Colores
COLOR_FONDO = (15, 15, 35)
COLOR_ACENTO = (255, 0, 110)
COLOR_TEXTO = (255, 255, 255)
COLOR_SUB = (160, 160, 160)

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None: default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except:
            pass
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

# =============================================================================
# GESTIÓN DE HISTORIAL
# =============================================================================

def cargar_historial():
    default = {
        'compartidas': [],
        'posts_usados': [],
        'timestamps': [],
        'hoy': 0,
        'fecha': None,
        'ultima': None,
        'total_historias': 0
    }
    return cargar_json(HISTORIAS_PATH, default)

def guardar_historia(historial, post_id):
    hoy = datetime.now().strftime('%Y-%m-%d')
    ahora = datetime.now().isoformat()
    
    if historial.get('fecha') != hoy:
        historial['hoy'] = 0
        historial['compartidas'] = []
        historial['fecha'] = hoy
    
    historial['compartidas'].append(post_id)
    historial['posts_usados'].append(post_id)
    historial['timestamps'].append(ahora)
    historial['hoy'] += 1
    historial['total_historias'] += 1
    historial['ultima'] = ahora
    
    if len(historial['posts_usados']) > 50:
        historial['posts_usados'] = historial['posts_usados'][-50:]
    
    guardar_json(HISTORIAS_PATH, historial)
    return historial

def verificar_intervalo():
    historial = cargar_historial()
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if historial.get('fecha') != hoy:
        historial = {
            'compartidas': [],
            'posts_usados': historial.get('posts_usados', [])[-20:],
            'timestamps': [],
            'hoy': 0,
            'fecha': hoy,
            'ultima': None,
            'total_historias': historial.get('total_historias', 0)
        }
        guardar_json(HISTORIAS_PATH, historial)
    
    if historial['hoy'] >= MAX_HISTORIAS_DIA:
        log(f"🚫 Límite {MAX_HISTORIAS_DIA} historias/día alcanzado", 'advertencia')
        return False, historial
    
    ultima = historial.get('ultima')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos_transcurridos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos_transcurridos < INTERVALO_MINUTOS:
                min_restantes = int(INTERVALO_MINUTOS - minutos_transcurridos)
                log(f"⏱️ Esperar {min_restantes}min para próxima historia", 'info')
                return False, historial
        except:
            pass
    
    return True, historial

# =============================================================================
# OBTENER POSTS DE FACEBOOK
# =============================================================================

def obtener_posts():
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return []
    
    try:
        fecha_limite = (datetime.now() - timedelta(days=DIAS_ATRAS)).strftime('%Y-%m-%d')
        
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/posts"
        params = {
            'access_token': FB_ACCESS_TOKEN,
            'fields': 'id,message,created_time,full_picture,permalink_url',
            'since': fecha_limite,
            'limit': 50
        }
        
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if 'error' in data:
            log(f"❌ Error API: {data['error'].get('message', 'Unknown')}", 'error')
            return []
        
        posts = []
        for post in data.get('data', []):
            mensaje = post.get('message', '')
            if not mensaje or len(mensaje) < 10:
                continue
            
            posts.append({
                'id': post['id'],
                'mensaje': mensaje,
                'fecha': post.get('created_time', ''),
                'imagen_url': post.get('full_picture', ''),
                'permalink': post.get('permalink_url', ''),
                'titulo': mensaje[:100]
            })
        
        log(f"📚 {len(posts)} posts disponibles", 'info')
        return posts
        
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return []

def seleccionar_post(posts, historial):
    usados = historial.get('posts_usados', [])
    candidatos = [p for p in posts if p['id'] not in usados]
    
    if not candidatos:
        log("⚠️ Todos usados, permitiendo repetición...", 'advertencia')
        fecha_limite = (datetime.now() - timedelta(days=7)).isoformat()
        candidatos = [p for p in posts if p['fecha'] < fecha_limite]
    
    if not candidatos:
        candidatos = posts
    
    if not candidatos:
        return None
    
    candidatos.sort(key=lambda x: x['fecha'])
    return random.choice(candidatos[:10])

# =============================================================================
# CREAR CONTENIDO
# =============================================================================

def crear_texto(post):
    templates = [
        "🔥 ¿Te perdiste esto?\n\n👆 Link en bio",
        "🎌 Reviviendo clásicos...\n\n✨ ¿Lo viste?",
        "📢 Recordatorio anime\n\n🔥 ¿Opiniones? 👆",
        "✨ Vuelve a verlo\n\n🎌 Link en la bio",
        "🔥 ¿Ya lo viste?\n\n👆 Más info en bio",
        "🎌 Clásico del día\n\n✨ ¿Te gustó? 👆",
        "📰 Releyendo...\n\n🔥 ¿Qué les pareció? 👆",
        "✨ ¿Lo compartiste?\n\n🎌 Link en bio 🔥"
    ]
    return random.choice(templates)

def descargar_imagen(url):
    if not url:
        return None
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        if 'image' not in resp.headers.get('content-type', ''):
            return None
        from io import BytesIO
        return Image.open(BytesIO(resp.content))
    except:
        return None

def crear_imagen_historia(post):
    ANCHO, ALTO = 1080, 1920
    
    img = Image.new('RGB', (ANCHO, ALTO), COLOR_FONDO)
    draw = ImageDraw.Draw(img)
    
    # Fuentes
    fuentes = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf"
    ]
    
    fuente_titulo = fuente_sub = fuente_small = None
    for f in fuentes:
        try:
            if os.path.exists(f):
                fuente_titulo = ImageFont.truetype(f, 70)
                fuente_sub = ImageFont.truetype(f, 45)
                fuente_small = ImageFont.truetype(f, 35)
                break
        except:
            continue
    
    if not fuente_titulo:
        fuente_titulo = fuente_sub = fuente_small = ImageFont.load_default()
    
    # Imagen original
    imagen_original = descargar_imagen(post.get('imagen_url', ''))
    
    if imagen_original:
        img_procesada = imagen_original.convert('RGB')
        ratio_orig = img_procesada.width / img_procesada.height
        ratio_target = ANCHO / ALTO
        
        if ratio_orig > ratio_target:
            new_height = ALTO
            new_width = int(new_height * ratio_orig)
        else:
            new_width = ANCHO
            new_height = int(new_width / ratio_orig)
        
        img_procesada = img_procesada.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        left = (new_width - ANCHO) // 2
        top = (new_height - ALTO) // 2
        img_procesada = img_procesada.crop((left, top, left + ANCHO, top + ALTO))
        
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(img_procesada)
        img_procesada = enhancer.enhance(0.4)
        
        img.paste(img_procesada, (0, 0))
    else:
        # Fondo degradado
        for y in range(ALTO):
            r = int(15 + (y / ALTO) * 40)
            g = int(15 + (y / ALTO) * 20)
            b = int(35 + (y / ALTO) * 60)
            draw.line([(0, y), (ANCHO, y)], fill=(r, g, b))
        
        draw.rectangle([(0, 0), (ANCHO, 15)], fill=COLOR_ACENTO)
        draw.rectangle([(0, ALTO-15), (ANCHO, ALTO)], fill=COLOR_ACENTO)
    
    # Título
    titulo = post['mensaje'][:70]
    if len(titulo) > 60:
        titulo = titulo[:60].rsplit(' ', 1)[0] + "..."
    
    lineas = textwrap.wrap(titulo, width=18)
    if len(lineas) > 3:
        lineas = lineas[:3]
        lineas[-1] += "..."
    
    y_pos = 500 if imagen_original else 600
    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente_titulo)
        ancho_texto = bbox[2] - bbox[0]
        x = (ANCHO - ancho_texto) // 2
        draw.text((x+3, y_pos+3), linea, font=fuente_titulo, fill=(0, 0, 0))
        draw.text((x, y_pos), linea, font=fuente_titulo, fill=COLOR_TEXTO)
        y_pos += 90
    
    # CTA
    y_cta = 1400 if imagen_original else 1300
    textos_cta = ["👆 Link en bio", "🔥 ¿Lo viste?", "✨ Revívelo aquí 👆"]
    cta = random.choice(textos_cta)
    
    bbox = draw.textbbox((0, 0), cta, font=fuente_sub)
    ancho_cta = bbox[2] - bbox[0]
    x_cta = (ANCHO - ancho_cta) // 2
    
    padding = 20
    draw.rectangle(
        [(x_cta - padding, y_cta - padding), 
         (x_cta + ancho_cta + padding, y_cta + bbox[3] - bbox[1] + padding)],
        fill=(0, 0, 0)
    )
    draw.text((x_cta, y_cta), cta, font=fuente_sub, fill=COLOR_ACENTO)
    
    # Marca
    draw.text((ANCHO//2, 1800), "🎌 Nuevo Anime", font=fuente_small, fill=COLOR_SUB, anchor='mm')
    
    # Guardar
    timestamp = datetime.now().strftime("%H%M%S")
    path = f'/tmp/historia_{timestamp}.jpg'
    img.save(path, 'JPEG', quality=95)
    
    return path

# =============================================================================
# PUBLICAR
# =============================================================================

def publicar_facebook(imagen_path, texto=""):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales", 'error')
        return False
    
    try:
        # Subir imagen
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img_file:
            files = {'file': ('historia.jpg', img_file, 'image/jpeg')}
            data = {
                'access_token': FB_ACCESS_TOKEN,
                'published': 'false',
                'temporary': 'true',
            }
            if texto:
                data['caption'] = texto[:200]
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Imagen subida: {result['id']}", 'exito')
            return True
        
        # Fallback: publicar como post normal
        log("⚠️ Intentando método alternativo...", 'advertencia')
        return publicar_alternativo(imagen_path, texto)
        
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False

def publicar_alternativo(imagen_path, texto):
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img_file:
            files = {'file': ('historia.jpg', img_file, 'image/jpeg')}
            data = {
                'access_token': FB_ACCESS_TOKEN,
                'message': texto[:500] if texto else '🎌 Historia del día',
                'published': 'true'
            }
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
        
        if 'id' in result or 'post_id' in result:
            post_id = result.get('post_id', result.get('id'))
            log(f"✅ Publicado (alternativa): {post_id}", 'exito')
            return True
        
        return False
        
    except Exception as e:
        log(f"❌ Error alternativo: {e}", 'error')
        return False

def publicar_instagram(imagen_path):
    if not IG_ACCOUNT_ID:
        return False
    
    try:
        # Crear media
        url = f"https://graph.facebook.com/v22.0/{IG_ACCOUNT_ID}/media"
        
        with open(imagen_path, 'rb') as img:
            files = {'file': ('story.jpg', img, 'image/jpeg')}
            data = {
                'access_token': FB_ACCESS_TOKEN,
                'media_type': 'STORIES'
            }
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
        
        if 'id' not in result:
            return False
        
        # Publicar
        publish_url = f"https://graph.facebook.com/v22.0/{IG_ACCOUNT_ID}/media_publish"
        publish_data = {
            'creation_id': result['id'],
            'access_token': FB_ACCESS_TOKEN
        }
        
        pub_resp = requests.post(publish_url, data=publish_data, timeout=30)
        pub_result = pub_resp.json()
        
        if 'id' in pub_result:
            log(f"✅ IG Story: {pub_result['id']}", 'exito')
            return True
        
        return False
        
    except Exception as e:
        log(f"❌ Error IG: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("📱 BOT HISTORIAS ANIME V2.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 {MAX_HISTORIAS_DIA} historias/día | Intervalo: {INTERVALO_MINUTOS}min")
    print("="*70)
    
    puede, historial = verificar_intervalo()
    if not puede:
        return False
    
    log(f"📈 Hoy: {historial['hoy']}/{MAX_HISTORIAS_DIA}", 'info')
    
    posts = obtener_posts()
    if not posts:
        return False
    
    post = seleccionar_post(posts, historial)
    if not post:
        return False
    
    log(f"🎯 Seleccionado: {post['mensaje'][:50]}...", 'info')
    
    texto = crear_texto(post)
    log(f"✍️ Texto: {texto[:50]}...", 'debug')
    
    log("🎨 Creando imagen...", 'info')
    imagen_path = crear_imagen_historia(post)
    
    if not imagen_path:
        return False
    
    print(f"\n{'='*60}")
    print("📱 PREVIEW:")
    print(f"{'='*60}")
    print(f"Texto: {texto}")
    print(f"Post: {post['permalink']}")
    print(f"{'='*60}")
    
    log("📤 Publicando...", 'info')
    
    exito_fb = publicar_facebook(imagen_path, texto)
    exito_ig = publicar_instagram(imagen_path) if IG_ACCOUNT_ID else False
    
    try:
        if os.path.exists(imagen_path):
            os.remove(imagen_path)
    except:
        pass
    
    if exito_fb or exito_ig:
        historial = guardar_historia(historial, post['id'])
        
        plataformas = []
        if exito_fb: plataformas.append("FB")
        if exito_ig: plataformas.append("IG")
        
        log(f"✅ Historia #{historial['hoy']} en: {', '.join(plataformas)}", 'exito')
        
        proxima = datetime.now() + timedelta(minutes=INTERVALO_MINUTOS)
        log(f"⏰ Próxima: ~{proxima.strftime('%H:%M')}", 'info')
        
        return True
    else:
        log("❌ Falló publicación", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("🛑 Interrumpido", 'advertencia')
        exit(0)
    except Exception as e:
        log(f"💥 Error: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
