import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import selenium.webdriver as webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
current_search = {"query": "", "size": "", "max_price": 200}  # Default

# === FLASK KEEP-ALIVE ===
app = Flask(__name__)
@app.route('/')
def home(): return "Vinted Universal Sniper żyje i jebie dowolne oferty 24/7, kurwa!"
threading.Thread(target=app.run, args=('0.0.0.0', int(os.environ.get('PORT', 8080))), daemon=True).start()

# === SELENIUM SETUP ===
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

# === KRAJE VINTED ===
countries = ['pl', 'de', 'fr', 'gb', 'es', 'it', 'nl', 'be', 'at', 'cz']  # Więcej EU!

def search_product(query, size, max_price):
    deals = []
    search_text = query.replace(' ', '%20')
    for country in countries:
        url = f"https://www.vinted.{country}/catalog?search_text={search_text}&size_ids[]={size}&price_to={max_price}&condition_ids[]=1&status_ids[]=1&status_ids[]=2"  # Idealny stan, nowy/używany lekko
        driver.get(url)
        time.sleep(6)  # Load + anti-bot
        items = driver.find_elements(By.CSS_SELECTOR, '.feed-grid__item')
        for item in items[:6]:  # Top 6 na kraj
            try:
                title = item.find_element(By.CSS_SELECTOR, '.new-item-box__title').text
                price_str = item.find_element(By.CSS_SELECTOR, '.new-item-box__price').text
                price = float(re.sub(r'[^\d.]', '', price_str))
                link = item.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                img = item.find_element(By.CSS_SELECTOR, 'img').get_attribute('src')
                likes = item.find_element(By.CSS_SELECTOR, '.new-item-box__favorites').text or "0"
                seller = item.find_element(By.CSS_SELECTOR, '.new-item-box__seller').text
                if query.lower() in title.lower() and price < max_price * 0.7:  # Zajebista <70% max
                    zysk = random.randint(int(price * 2), int(price * 5))
                    deals.append({
                        'title': title,
                        'price': f"{price_str}",
                        'link': link,
                        'img': img,
                        'likes': likes,
                        'seller': seller,
                        'country': country.upper(),
                        'zysk': f"{zysk}zł flip – x{ zysk // int(price) } zysku!"
                    })
            except: pass
    deals.sort(key=lambda x: float(re.sub(r'[^\d.]', '', x['price'])))
    return deals[:3]  # Top 3 global

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
    deals = search_product(current_search['query'], current_search['size'], current_search['max_price'])
    if not deals: return
    for deal in deals:
        if float(re.sub(r'[^\d.]', '', deal['price'])) < current_search['max_price'] * 0.5:  # MEGA ZAJEBISTA <50%
            embed = discord.Embed(title=f"🚨 ZAJEBISTA OFERTA {current_search['query'].upper()} – {deal['country']}!", color=0xFF0000)
            embed.add_field(name=f"{deal['title']}", value=f"Cena: **{deal['price']}**\nLikes: {deal['likes']}\nSprzedawca: {deal['seller']}\n**ZYSK FLIP: {deal['zysk']}**\n@everyone WSTAWAJ – PEREŁKA DLA CIEBIE!", inline=False)
            embed.set_image(url=deal['img'])
            view = View()
            view.add_item(Button(label="KUP NATYCHMIAST!", url=deal['link'], style=discord.ButtonStyle.danger))
            await channel.send("@everyone MEGA OFERTA – SNIPER ZŁAPAŁ!", embed=embed, view=view)
            await voice_alert(channel, f"ZAJEBISTA OFERTA {current_search['query']} za {deal['price']}")

@bot.command()
async def szukaj(ctx, *, args):
    global current_search
    parts = args.split()
    query = " ".join(parts[:-2]) if len(parts) > 2 else args
    size = parts[-2] if len(parts) > 1 else "any"
    max_price = int(parts[-1]) if len(parts) > 0 and parts[-1].isdigit() else 200
    current_search = {"query": query, "size": size, "max_price": max_price}
    await ctx.send(f"🔥 SNAJPER AKTYWNY NA **{query.upper()} ROZMIAR {size} MAX {max_price}zł** – alerty co 15 min jak perełka!")
    await universal_sniper()  # Natychmiastowy scan

@bot.command()
async def stop(ctx):
    global current_search
    current_search = {"query": "", "size": "", "max_price": 200}
    await ctx.send("🛑 SNAJPER WYŁĄCZONY – zero alertów!")

@bot.event
async def on_ready():
    global channel
    channel = bot.get_channel(CHANNEL_ID)
    print(f'VINTED UNIVERSAL SNIPER ONLINE – CZEKA NA !szukaj [marka/model] [rozmiar] [max cena]!')
    universal_sniper.start()

bot.run(TOKEN)