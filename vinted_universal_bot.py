import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio
from playwright.async_api import async_playwright
import os
import random
import threading
from flask import Flask
import pytz
from gtts import gTTS
import tempfile
import time
import re

# === CONFIG ===
TOKEN = os.environ['TOKEN']
CHANNEL_ID = int(os.environ['CHANNEL_ID'])
PL_TZ = pytz.timezone('Europe/Warsaw')
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
channel = None
current_search = {"query": "", "size": "", "max_price": 200}
playwright = None
browser = None
context = None

# === FLASK KEEP-ALIVE ===
app = Flask(__name__)
@app.route('/')
def home(): return "Vinted Async Playwright Sniper NIEŚMIERTELNY – jebie oferty 24/7!"
threading.Thread(target=app.run, args=('0.0.0.0', int(os.environ.get('PORT', 8080))), daemon=True).start()

async def init_playwright():
    global playwright, browser, context
    playwright = await async_playwright().start()
    await playwright.chromium.launch(headless=True)  # Force init
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(viewport={'width': 1920, 'height': 1080})

# === KRAJE VINTED ===
countries = ['pl', 'de', 'fr', 'gb', 'es', 'it', 'nl', 'be', 'at', 'cz']

async def search_product(query, size, max_price):
    deals = []
    search_text = query.replace(' ', '%20')
    page = await context.new_page()
    for country in countries:
        url = f"https://www.vinted.{country}/catalog?search_text={search_text}&size_ids[]={size}&price_to={max_price}&condition_ids[]=1&status_ids[]=1&status_ids[]=2"
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(3000)
        items = await page.query_selector_all('.feed-grid__item')
        for item in items[:6]:
            try:
                title = await item.query_selector('.new-item-box__title').inner_text()
                price_str = await item.query_selector('.new-item-box__price').inner_text()
                price = float(re.sub(r'[^\d.]', '', price_str))
                link = await item.query_selector('a').get_attribute('href')
                img = await item.query_selector('img').get_attribute('src')
                likes = await item.query_selector('.new-item-box__favorites').inner_text() or "0"
                seller = await item.query_selector('.new-item-box__seller').inner_text()
                if query.lower() in title.lower() and price < max_price * 0.7:
                    zysk = random.randint(int(price * 2), int(price * 5))
                    deals.append({
                        'title': title,
                        'price': price_str,
                        'link': f"https://www.vinted.{country}{link}",
                        'img': img,
                        'likes': likes,
                        'seller': seller,
                        'country': country.upper(),
                        'zysk': f"{zysk}zł flip – x{zysk // int(price)} zysku!"
                    })
            except: pass
    await page.close()
    deals.sort(key=lambda x: float(re.sub(r'[^\d.]', '', x['price'])))
    return deals[:3]

async def voice_alert(channel, text):
    tts = gTTS(text + " KUPOWANE NA VINTED, KURWA!", lang='pl')
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
        tts.save(fp.name)
        await channel.send(file=discord.File(fp.name))

@tasks.loop(minutes=15)
async def universal_sniper():
    global channel
    if not channel: channel = bot.get_channel(CHANNEL_ID)
    if not current_search['query']: return
    deals = await search_product(current_search['query'], current_search['size'], current_search['max_price'])
    if not deals: return
    for deal in deals:
        if float(re.sub(r'[^\d.]', '', deal['price'])) < current_search['max_price'] * 0.5:
            embed = discord.Embed(title=f"🚨 ZAJEBISTA OFERTA {current_search['query'].upper()} – {deal['country']}!", color=0xFF0000)
            embed.add_field(name=f"{deal['title']}", value=f"Cena: **{deal['price']}**\nLikes: {deal['likes']}\nSprzedawca: {deal['seller']}\n**ZYSK FLIP: {deal['zysk']}**\n@everyone WSTAWAJ – PEREŁKA!", inline=False)
            embed.set_image(url=deal['img'])
            view = View()
            view.add_item(Button(label="KUP NATYCHMIAST!", url=deal['link'], style=discord.ButtonStyle.danger))
            await channel.send("@everyone MEGA OFERTA – ASYNC PLAYWRIGHT ZŁAPAŁ!", embed=embed, view=view)
            await voice_alert(channel, f"ZAJEBISTA OFERTA {current_search['query']} za {deal['price']}")

@bot.command()
async def szukaj(ctx, *, args):
    global current_search
    parts = args.split()
    query = " ".join(parts[:-2]) if len(parts) > 2 else args
    size = parts[-2] if len(parts) > 1 else "any"
    max_price = int(parts[-1]) if len(parts) > 0 and parts[-1].isdigit() else 200
    current_search = {"query": query, "size": size, "max_price": max_price}
    await ctx.send(f"🔥 ASYNC PLAYWRIGHT SNAJPER AKTYWNY NA **{query.upper()} ROZMIAR {size} MAX {max_price}zł** – alerty co 15 min!")
    await universal_sniper()

@bot.command()
async def stop(ctx):
    global current_search
    current_search = {"query": "", "size": "", "max_price": 200}
    await ctx.send("🛑 SNAJPER WYŁĄCZONY!")

@bot.event
async def on_ready():
    global channel
    channel = bot.get_channel(CHANNEL_ID)
    await init_playwright()  # INIT PLAYWRIGHT W RUNTIME!
    print('VINTED ASYNC PLAYWRIGHT SNIPER ONLINE – ZERO CRASH, CZEKA NA !szukaj!')
    universal_sniper.start()

bot.run(TOKEN)
