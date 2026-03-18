#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Historias Anime V1.0
Comparte publicaciones antiguas en historias de Facebook/Instagram
Ejecutar cada 4-6 horas (no tan frecuente como posts)
"""

import requests
import json
import os
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
IG_ACCOUNT_ID = os.getenv('IG_ACCOUNT_ID')  # Opcional para Instagram

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_POSTS_PATH = os.path.join(BASE_DIR, 'data', 'historial_anime.json')
HISTORIAS_PATH = os.path.join(BASE_DIR, 'data', 'historial_historias.json')

# Cada cuanto compartir historias (en horas)
INTERVALO_HISTORIAS = 4  # 4 horas = 6 historias/día máximo
MAX_HISTORIAS_DIA = 6

# Cuántos días atrás buscar posts para compartir
DIAS_ATRAS = 7  # Posts de la última semana

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None: default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except: pass
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

def cargar_historial_historias():
    """Carga el historial de historias ya compartidas"""
    default = {
        'compartidas': [],  # IDs de posts ya compartidos
        'timestamps': [],
        'hoy': 0,
        'fecha': None,
        'ultima': None
    }
    return cargar_json(HISTORIAS_PATH, default)

def guardar_historia_compartida(historial, post_id):
    """Registra una historia compartida"""
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if historial.get('fecha') != hoy:
        historial['hoy'] = 0
        historial['fecha'] = hoy
    
    historial['compartidas'].append(post_id)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['hoy'] += 1
    historial['ultima'] = datetime.now().isoformat()
    
    # Mantener solo últimas 100
    if len(historial['compartidas']) > 100:
        historial['compartidas'] = historial['compartidas'][-100:]
        historial['timestamps'] = historial['timestamps'][-100:]
    
    guardar_json(HISTORIAS_PATH, historial)
    return historial

def verificar_intervalo():
    """Verifica si ha pasado el tiempo mínimo entre historias"""
    historial = cargar_historial_historias()
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    # Reset diario
    if historial.get('fecha') != hoy:
        historial = {'compartidas': [], 'timestamps': [], 'hoy': 0, 'fecha': hoy, 'ultima': None}
    
    # Verificar límite diario
    if historial['hoy'] >= MAX_HISTORIAS_DIA:
        log(f"🚫 Límite de {MAX_HISTORIAS_DIA} historias/día alcanzado", 'advertencia')
        return False, historial
    
    # Verificar tiempo entre historias
    ultima = historial.get('ultima')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            horas = (datetime.now() - ultima_dt).total_seconds() / 3600
            if horas < INTERVALO_HISTORIAS:
                min_restantes = int((INTERVALO_HISTORIAS - horas) * 60)
                log(f"⏱️ Esperar {min_restantes}min para próxima historia", 'info')
                return False, historial
        except: pass
    
    return True, historial

# =============================================================================
# OBTENER POSTS ANTIGUOS
# =============================================================================

def obtener_posts_recientes():
    """Obtiene posts publicados por el bot en los últimos días"""
    try:
        # Cargar historial del bot principal
        posts_hist = cargar_json(HISTORIAL_POSTS_PATH, {'urls': [], 'titulos': [], 'timestamps': []})
        
        if not posts_hist.get('timestamps'):
            log("❌ No hay posts en el historial", 'error')
            return []
        
        posts_validos = []
        ahora = datetime.now()
        limite_dias = timedelta(days=DIAS_ATRAS)
        
        for i, ts in enumerate(posts_hist['timestamps']):
            try:
                post_fecha = datetime.fromisoformat(ts)
                # Solo posts de los últimos X días
                if (ahora - post_fecha) <= limite_dias:
                    posts_validos.append({
                        'titulo': posts_hist['titulos'][i] if i < len(posts_hist['titulos']) else "Anime",
                        'url': posts_hist['urls'][i] if i < len(posts_hist['urls']) else "",
                        'fecha': ts,
                        'id': i
                    })
            except: continue
        
        # Ordenar por más recientes primero
        posts_validos.sort(key=lambda x: x['fecha'], reverse=True)
        log(f"📚 {len(posts_validos)} posts disponibles (últimos {DIAS_ATRAS} días)", 'info')
        return posts_validos
        
    except Exception as e:
        log(f"❌ Error cargando posts: {e}", 'error')
        return []

def seleccionar_post_para_historia(posts_disponibles, ya_compartidos):
    """Selecciona un post que no haya sido compartido recientemente"""
    # Filtrar los ya compartidos
    candidatos = [p for p in posts_disponibles if p['id'] not in ya_compartidos]
    
    if not candidatos:
        log("⚠️ Todos los posts ya fueron compartidos, reiniciando...", 'advertencia')
        # Si todos fueron compartidos, tomar el más antiguo de los recientes
        candidatos = posts_disponibles[-3:] if len(posts_disponibles) >= 3 else posts_disponibles
    
    if not candidatos:
        return None
    
    # Seleccionar aleatoriamente entre los 3 más recientes no compartidos
    return random.choice(candidatos[:3])

# =============================================================================
# CREAR CONTENIDO PARA HISTORIA
# =============================================================================

def crear_texto_historia(post):
    """Crea texto corto y atractivo para historia"""
    
    titulo = post['titulo'][:50] if len(post['titulo']) > 50 else post['titulo']
    
    templates = [
        f"🔥 ¿Te perdiste esto?\n\n🎌 {titulo}\n\n👆 Link en bio",
        f"📢 Recordatorio\n\n✨ {titulo}\n\n💬 ¿Ya lo viste?",
        f"🎌 Vuelve a ver\n\n🔥 {titulo}\n\n👇 Más info",
        f"✨ Clásico reciente\n\n🎌 {titulo}\n\n🔥 ¿Opiniones?",
        f"📰 Releyendo...\n\n🎌 {titulo}\n\n💭 ¿Qué les pareció?"
    ]
    
    return random.choice(templates)

def descargar_imagen_para_historia(image_url):
    """Descarga y prepara imagen para historia (9:16 o 1:1)"""
    if not image_url:
        return None
    
    try:
        from PIL import Image
        from io import BytesIO
        
        # Descargar
        r = requests.get(image_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        if 'image' not in r.headers.get('content-type', ''):
            return None
        
        img = Image.open(BytesIO(r.content))
        
        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize para historia (9:16 ratio o 1080x1920)
        # O 1:1 para Feed como historia
        target_size = (1080, 1920)  # Vertical historia
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Crear canvas vertical y centrar imagen
        canvas = Image.new('RGB', target_size, (15, 15, 35))
        x = (target_size[0] - img.width) // 2
        y = (target_size[1] - img.height) // 2
        canvas.paste(img, (x, y))
        
        path = f'/tmp/historia_{datetime.now().strftime("%H%M%S")}.jpg'
        canvas.save(path, 'JPEG', quality=90)
        
        return path
        
    except Exception as e:
        log(f"⚠️ Error preparando imagen: {e}", 'advertencia')
        return None

# =============================================================================
# PUBLICAR EN HISTORIAS (FACEBOOK)
# =============================================================================

def publicar_historia_facebook(texto, imagen_path):
    """Publica en historias de Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    
    try:
        # Facebook Stories API (requiere permisos especiales)
        # Nota: La API de historias de FB es limitada, alternativa usar posts efímeros
        
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img:
            files = {'file': ('historia.jpg', img, 'image/jpeg')}
            data = {
                'message': texto[:500],  # Historias permiten menos texto
                'access_token': FB_ACCESS_TOKEN,
                'published': 'false',  # No publicar en feed, solo historia si es posible
                'temporary_image': 'true'  # Intentar marcar como temporal
            }
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Historia publicada: {result['id']}", 'exito')
            return True
        
        error = result.get('error', {})
        log(f"❌ Error FB: {error.get('message', 'Unknown')}", 'error')
        return False
        
    except Exception as e:
        log(f"❌ Error publicando historia: {e}", 'error')
        return False

def publicar_story_instagram(texto, imagen_path):
    """Publica en historias de Instagram (requiere IG Business API)"""
    if not IG_ACCOUNT_ID:
        log("⚠️ Sin IG_ACCOUNT_ID, saltando Instagram", 'advertencia')
        return False
    
    try:
        # Instagram Stories API
        # Paso 1: Subir imagen
        url = f"https://graph.facebook.com/v22.0/{IG_ACCOUNT_ID}/media"
        
        with open(imagen_path, 'rb') as img:
            files = {'file': ('story.jpg', img, 'image/jpeg')}
            data = {
                'access_token': FB_ACCESS_TOKEN,
                'media_type': 'STORIES'
            }
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
        
        if 'id' in result:
            creation_id = result['id']
            
            # Paso 2: Publicar historia
            publish_url = f"https://graph.facebook.com/v22.0/{IG_ACCOUNT_ID}/media_publish"
            publish_data = {
                'creation_id': creation_id,
                'access_token': FB_ACCESS_TOKEN
            }
            
            pub_resp = requests.post(publish_url, data=publish_data, timeout=30)
            pub_result = pub_resp.json()
            
            if 'id' in pub_result:
                log(f"✅ IG Story publicada: {pub_result['id']}", 'exito')
                return True
        
        error = result.get('error', {})
        log(f"❌ Error IG: {error.get('message', 'Unknown')}", 'error')
        return False
        
    except Exception as e:
        log(f"❌ Error IG: {e}", 'error')
        return False

# =============================================================================
# ALTERNATIVA: POST EFÍMERO (REELS/STORIES HACK)
# =============================================================================

def publicar_como_reel(post, imagen_path):
    """Alternativa: Publicar como Reel corto si historias no funcionan"""
    # Los Reels tienen mejor alcance que historias y duran 24h en destacados
    
    texto = crear_texto_historia(post)
    
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/videos"
        
        with open(imagen_path, 'rb') as video_file:
            files = {'file': ('reel.mp4', video_file, 'video/mp4')}
            data = {
                'description': texto[:200],
                'access_token': FB_ACCESS_TOKEN
            }
            
            resp = requests.post(url, files=files, data=data, timeout=120)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Reel publicado: {result['id']}", 'exito')
            return True
        return False
        
    except Exception as e:
        log(f"❌ Error reel: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("📱 BOT HISTORIAS ANIME V1.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Intervalo: {INTERVALO_HISTORIAS}h | Máx: {MAX_HISTORIAS_DIA}/día")
    print("="*70)
    
    # Verificar si toca publicar
    puede, historial = verificar_intervalo()
    if not puede:
        return False
    
    log(f"📊 Historias hoy: {historial.get('hoy', 0)}/{MAX_HISTORIAS_DIA}", 'info')
    
    # Obtener posts disponibles
    posts = obtener_posts_recientes()
    if not posts:
        log("❌ No hay posts para compartir", 'error')
        return False
    
    # Seleccionar uno no compartido recientemente
    post = seleccionar_post_para_historia(posts, historial.get('compartidas', []))
    if not post:
        log("❌ No se pudo seleccionar post", 'error')
        return False
    
    log(f"🎯 Seleccionado: {post['titulo'][:50]}...", 'info')
    
    # Crear contenido
    texto = crear_texto_historia(post)
    
    # Intentar obtener imagen del post original
    # (Aquí necesitarías guardar las URLs de imágenes en el historial principal)
    # Por ahora usamos imagen genérica o la del post si está disponible
    
    # Crear imagen para historia
    from PIL import Image, ImageDraw, ImageFont
    import textwrap
    
    # Crear imagen vertical estilo historia
    img = Image.new('RGB', (1080, 1920), color='#0f0f23')
    draw = ImageDraw.Draw(img)
    
    # Fondo degradado simple
    for y in range(1920):
        color = (15 + y//100, 15, 35 + y//50)
        draw.line([(0, y), (1080, y)], fill=color)
    
    # Texto
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except:
        font = font_small = ImageFont.load_default()
    
    # Título centrado
    titulo_wrapped = textwrap.fill(post['titulo'][:80], width=20)
    lines = titulo_wrapped.split('\n')
    y_pos = 600
    
    for line in lines:
        draw.text((540, y_pos), line, font=font, fill='#ffffff', anchor='mm')
        y_pos += 80
    
    # Subtítulo
    draw.text((540, 1000), "🔥 ¿Te lo perdiste?", font=font_small, fill='#ff006e', anchor='mm')
    draw.text((540, 1100), "👆 Link en la bio", font=font_small, fill='#a0a0a0', anchor='mm')
    
    # Guardar
    img_path = f'/tmp/historia_{datetime.now().strftime("%H%M%S")}.jpg'
    img.save(img_path, 'JPEG', quality=95)
    
    print(f"\n📱 CONTENIDO CREADO:")
    print(f"{'='*50}")
    print(texto)
    print(f"{'='*50}")
    
    # Publicar
    log("📤 Publicando historia...", 'info')
    
    # Intentar Facebook
    exito_fb = publicar_historia_facebook(texto, img_path)
    
    # Intentar Instagram si está configurado
    exito_ig = False
    if IG_ACCOUNT_ID:
        exito_ig = publicar_story_instagram(texto, img_path)
    
    # Limpiar
    try:
        if os.path.exists(img_path):
            os.remove(img_path)
    except: pass
    
    # Registrar
    if exito_fb or exito_ig:
        historial = guardar_historia_compartida(historial, post['id'])
        log(f"✅ Historia compartida. Total hoy: {historial['hoy']}", 'exito')
        return True
    else:
        log("❌ Falló publicación en ambas plataformas", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("🛑 Interrumpido", 'advertencia')
        exit(0)
    except Exception as e:
        log(f"💥 Crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
