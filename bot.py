import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import wikipediaapi
from newspaper import Article
import pickle
import os

TOKEN = "7056698579:AAFuDwSVHizm1OxB9C-8ocaZyyQIsJYHevc"

# ملف حفظ الأشخاص المفضلين
FOLLOW_FILE = "followed.pkl"

# تحميل الأشخاص المفضلين
if os.path.exists(FOLLOW_FILE):
    with open(FOLLOW_FILE, "rb") as f:
        followed = pickle.load(f)
else:
    followed = []

wiki_wiki = wikipediaapi.Wikipedia('en')

# ----- أوامر البوت -----

async def cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("❗ اكتب اسم الشخص بعد الأمر")
        return

    page = wiki_wiki.page(name)
    if not page.exists():
        await update.message.reply_text("❌ لم يتم العثور على صفحة ويكيبيديا لهذا الشخص")
        return

    text = page.text.split("\n")
    summary = "\n".join(text[:5])  # ملخص أول 5 أسطر
    msg = f"👤 *{page.title}*\n\n{summary}"

    # البحث عن الصورة
    soup = BeautifulSoup(requests.get(page.fullurl).text, "html.parser")
    img_tag = soup.find("table", {"class": "infobox"}).find("img") if soup.find("table", {"class": "infobox"}) else None
    if img_tag:
        img_url = "https:" + img_tag["src"]
        await update.message.reply_photo(photo=img_url, caption=msg)
    else:
        await update.message.reply_text(msg)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("❗ اكتب اسم الشخص بعد الأمر")
        return

    url = f"https://duckduckgo.com/html/?q={name}+news"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.find_all("a", class_="result__a")

    if not results:
        await update.message.reply_text("❌ لم يتم العثور على أخبار")
        return

    msg = f"📰 آخر الأخبار عن {name}:\n\n"
    for r in results[:3]:  # آخر 3 أخبار
        link = r.get("href")
        try:
            article = Article(link)
            article.download()
            article.parse()
            article.nlp()
            msg += f"• {article.title}\n{article.summary[:300]}...\n{link}\n\n"
        except:
            msg += f"• {r.text}\n{link}\n\n"

    await update.message.reply_text(msg)

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("❗ اكتب اسم الشخص بعد الأمر")
        return

    if name not in followed:
        followed.append(name)
        with open(FOLLOW_FILE, "wb") as f:
            pickle.dump(followed, f)
        await update.message.reply_text(f"✅ تم إضافة {name} لقائمة المتابعة")
    else:
        await update.message.reply_text(f"ℹ️ {name} موجود بالفعل في قائمة المتابعة")

async def list_followed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not followed:
        await update.message.reply_text("❌ لا يوجد أشخاص في قائمة المتابعة")
    else:
        msg = "⭐ الأشخاص الذين تتابعهم:\n\n"
        for i, person in enumerate(followed, 1):
            msg += f"{i}- {person}\n"
        await update.message.reply_text(msg)

# ----- تشغيل البوت -----
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("cv", cv))
app.add_handler(CommandHandler("news", news))
app.add_handler(CommandHandler("follow", follow))
app.add_handler(CommandHandler("list", list_followed))

print("🚀 البوت يعمل الآن...")
app.run_polling()
