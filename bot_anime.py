#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Anime V2.6 - Publica posts nuevos desde RSS
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

# Configuración
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

TIEMPO_ENTRE_PUBLICACIONES = 60
MAX_PUBLICACIONES_DIA = 24

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.path.join(BASE_DIR, 'data', 'historial_anime.json')

RSS_FEEDS = [
    'https://somoskudasai.com/feed/',
    'https://www.animenewsnetwork.com/all/rss.xml',
    'https://myanimelist.net/rss/news.xml',
]

PALABRAS_ANIME = {
    "jujutsu kaisen": 20, "demon slayer": 20, "kimetsu": 20,
    "attack on titan": 20, "one piece": 18, "my hero academia": 18,
}

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️'}
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

def generar_hash(texto):
    if not texto: return ""
    t = re.sub(r'[^\w\s]', '', texto.lower().strip())
    return hashlib.md5(re.sub(r'\s+', ' ', t).encode()).hexdigest()

def limpiar_texto(texto):
    if not texto: return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def redactar_manual(titulo, contenido, tipo="noticia"):
    hooks = {
        "noticia": ["📢 ¡Noticia importante!", "🔥 ¡Última hora!", "🎌 ¡Anuncio!"],
        "estreno": ["🚨 ¡Estreno!", "🎉 ¡Nuevo anime!", "✨ ¡Confirmado!"]
    }
    
    hook = random.choice(hooks.get(tipo, hooks["noticia"]))
    
    resumen = contenido[:200].strip()
    if len(resumen) > 180:
        resumen = resumen[:180].rsplit(' ', 1)[0] + "..."
    
    texto = f"""{hook}

🎌 {titulo[:70]}

📰 {resumen}

💬 ¿Qué opinan? ¡Los leo! 👇

#Anime #Otaku #Noticias"""
    
    return texto[:1500]

def obtener_noticias():
    noticias = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo:
                    continue
                
                desc = limpiar_texto(entry.get('summary', ''))
                
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': entry.get('link', ''),
                    'puntaje': sum(p for k, p in PALABRAS_ANIME.items() if k in (titulo + desc).lower())
                })
        except: continue
    
    return sorted(noticias, key=lambda x: x['puntaje'], reverse=True)

def publicar_facebook(mensaje):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
        data = {
            'message': mensaje[:2000],
            'access_token': FB_ACCESS_TOKEN
        }
        
        resp = requests.post(url, data=data, timeout=30)
        result = resp.json()
        
        return 'id' in result
    except:
        return False

def main():
    print("\n" + "="*50)
    print("🇯🇵 BOT ANIME - Posts Nuevos")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    historial = cargar_json(HISTORIAL_PATH, {'urls': [], 'hashes': [], 'hoy': 0, 'fecha': None})
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if historial.get('fecha') != hoy:
        historial = {'urls': [], 'hashes': [], 'hoy': 0, 'fecha': hoy}
    
    if historial['hoy'] >= MAX_PUBLICACIONES_DIA:
        log("🚫 Límite diario alcanzado", 'advertencia')
        return False
    
    noticias = obtener_noticias()
    if not noticias:
        log("❌ Sin noticias", 'error')
        return False
    
    for noticia in noticias:
        hash_titulo = generar_hash(noticia['titulo'])
        if hash_titulo in historial['hashes']:
            continue
        
        mensaje = redactar_manual(noticia['titulo'], noticia['descripcion'])
        
        log(f"📝 Publicando: {noticia['titulo'][:50]}...", 'info')
        
        if publicar_facebook(mensaje):
            historial['urls'].append(noticia['url'])
            historial['hashes'].append(hash_titulo)
            historial['hoy'] += 1
            guardar_json(HISTORIAL_PATH, historial)
            log("✅ Publicado", 'exito')
            return True
        else:
            log("❌ Error al publicar", 'error')
    
    return False

if __name__ == "__main__":
    exit(0 if main() else 1)
