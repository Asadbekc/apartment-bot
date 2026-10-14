import asyncio
import os
import re
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# 1. Telegram sozlamalari
API_ID = 32448035
API_HASH = "0f1d487ae1c82955576fd8d0a23cdec0"
SESSION_STRING = os.getenv("SESSION_STRING", "")

TARGET_CHANNELS = ["TOSHKENT_IJARAGA_UYLAR_MAKLERSIZ"]

# 2. Qidiruv va filtr parametrlari
MIN_PRICE = 350
MAX_PRICE = 550

LOCATION_KEYWORDS = [
    "shayxontohur",
    "шайхантахур",
    "shayxontoxur",
    "tashkent city",
    "ташкент сити",
    "city mall",
    "сити молл",
    "ganga",
    "ганга",
    "xadra",
    "хадра",
    "hadra",
    "xalqlar doʻstligi",
    "xalqlar dostligi",
    "drujba",
    "дружба",
    "дружбы",
    "g'ofur g'ulom",
    "gafur gulyam",
    "гафур гулям",
    "abay",
    "абай",
    "chorsu",
    "чорсу",
    "qoratosh",
    "кораташ",
    "paxtakor",
    "пахтакор",
    "alisher navoiy",
    "алишер навои",
    "sebzor",
    "себзор",
    "jangoh",
    "жангох",
    "ts-14",
    "ц-14",
    "ц-15",
    "novza",
    "новза",
    "chilonzor",
    "чилонзор",
]

ROOM_PATTERNS = [
    r"\b2\s*[-_]?\s*(xona|xonali|xonalik|hona|honali)\b",
    r"\b2\s*[-_]?\s*(ком|комн|комнат|комнатная|комнатную)\b",
    r"\b2\s*[-_]?\s*х\b",
    r"\b2/[-0-9/]+\b",
]

GIRLS_ONLY_KEYWORDS = [
    r"faqat\s+qizlar",
    r"talaba\s+qiz",
    r"qizlar\s+uchun",
    r"qizlarga\b",
    r"qiz\s+bolaga",
    r"ayollar\s+uchun",
    r"faqat\s+ayol",
    r"для\s+девушек",
    r"только\s+девушкам",
    r"студенткам\b",
    r"женскому\s+полу",
    r"девочкам\b",
]

FAMILY_KEYWORDS = [
    r"\boila(ga|viy|lar| uchun)?\b",
    r"\bsemya\b",
    r"\bсемейн(ым|ой|ые)\b",
    r"\bдля семьи\b",
    r"\bсемье\b",
    r"\bzags\b",
    r"\bzaks\b",
]

BOYS_KEYWORDS = [
    r"\b(o[\'’`]?g[\'’`]?il\s+)?bol(lar|larga|alar|alarga|aga)?\b",
    r"\byigit(lar|larga|ga)?\b",
    r"\bbolla(r|ga|rga)?\b",
    r"\bпарн(ям|ей|ю)\b",
    r"\bдля парней\b",
    r"\bмальчик(ам|ов)\b",
]


def check_is_girls_only(text: str) -> bool:
  t_lower = text.lower()
  if (
      "qizlarga emas" in t_lower
      or "qizlarga berilmaydi" in t_lower
      or "qizlar bezovta qilmasin" in t_lower
  ):
    return False
  return any(re.search(pat, t_lower) for pat in GIRLS_ONLY_KEYWORDS)


def get_tenant_type(text: str) -> str:
  t_lower = text.lower()
  is_fam = any(re.search(p, t_lower) for p in FAMILY_KEYWORDS)
  is_boy = any(re.search(p, t_lower) for p in BOYS_KEYWORDS)
  if is_fam and is_boy:
    return "Oilaga yoki o'g'il bolalarga"
  elif is_fam:
    return "Faqat oilaga (ZAGS bilan)"
  elif is_boy:
    return "O'g'il bolalarga / Yigitlarga"
  else:
    return "Hammasi uchun / Cheklovsiz"


def check_is_two_rooms(text: str) -> bool:
  text_lower = text.lower()
  return any(re.search(pattern, text_lower) for pattern in ROOM_PATTERNS)


def extract_price(text: str) -> int | None:
  text_lower = text.lower()
  m = re.search(r"(\d{3,4})\s*(\$|usd|у\.е|y\.e|ye)", text_lower)
  if m:
    return int(m.group(1))
  m2 = re.search(r"(\$)\s*(\d{3,4})", text_lower)
  if m2:
    return int(m2.group(2))
  m_som = re.search(
      r"(\d{1,2})[\s.,]?(\d{3})[\s.,]?000\s*(so[\'’`]?m|сум)", text_lower
  )
  if m_som:
    return int(m_som.group(1) + m_som.group(2) + "000") // 12800
  return None


def check_location(text: str) -> bool:
  text_lower = text.lower()
  return any(kw in text_lower for kw in LOCATION_KEYWORDS)


def is_matching_apartment(text: str) -> tuple[bool, str, str]:
  if not text:
    return False, "Matn yo'q", ""
  if check_is_girls_only(text):
    return False, "Qizlarga mo'ljallangan", ""
  if not check_is_two_rooms(text):
    return False, "2 xonali emas", ""
  price = extract_price(text)
  if price is not None and not (MIN_PRICE <= price <= MAX_PRICE):
    return False, f"Narx to'g'ri kelmadi: ${price}", ""
  if not check_location(text):
    return False, "Lokatsiya to'g'ri kelmadi", ""
  tenant_type = get_tenant_type(text)
  return True, f"Mos e'lon! (Narxi: ${price if price else 'Nomalum'})", tenant_type


client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@client.on(events.NewMessage(chats=TARGET_CHANNELS))
async def handler(event):
  is_match, reason, tenant_type = is_matching_apartment(event.raw_text)
  if is_match:
    channel = event.chat.username or event.chat.title
    alert = (
        f"🔔 Yangi mos kvartira topildi!\n"
        f"👥 Kimlar uchun: {tenant_type}\n"
        f"📍 Kanal: @{channel}\n"
        f"🎯 Tafsilot: {reason}\n"
        f"🔗 Havola: https://t.me/{channel}/{event.id}\n"
    )
    await client.send_message("me", alert)
    await event.forward_to("me")


async def handle_ping(request):
  return web.Response(text="Bot 24/7 ishlab turibdi!")


async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.getenv("PORT", 10000))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()
  print(f"Web server {port}-portda ishga tushdi.")


async def main():
  print("Bulutli bot ishga tushmoqda...")
  await client.start()
  await client.send_message(
      "me",
      "🚀 Assalomu alaykum! Botingiz Render bulutida 24/7 muvaffaqiyatli ishga"
      " tushdi!",
  )
  await start_web_server()
  print("Telegram kanallari 24/7 kuzatilmoqda...")
  await client.run_until_disconnected()


if __name__ == "__main__":
  asyncio.run(main())
