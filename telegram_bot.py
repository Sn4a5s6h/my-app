import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

from database.models import db, User
from app import app   # ⚠️ استيراد تطبيق Flask

BOT_TOKEN = "7056698579:AAFuDwSVHizm1OxB9C-8ocaZyyQIsJYHevc"

logging.basicConfig(level=logging.INFO)

# ⚠️ ضع ID حسابك في تليجرام فقط (للحماية)
ADMIN_TELEGRAM_IDS = "7057346640"


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_TELEGRAM_IDS:
            await update.message.reply_text("❌ غير مصرح لك")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 بوت إدارة المستخدمين\n\n"
        "/add_user email password role\n"
        "/list_users\n"
        "/activate email\n"
        "/deactivate email\n"
        "/reset_password email new_password"
    )


@admin_only
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        email, password, role = context.args
    except ValueError:
        await update.message.reply_text("❌ الاستخدام:\n/add_user email password role")
        return

    with app.app_context():
        if User.query.filter_by(email=email).first():
            await update.message.reply_text("⚠️ المستخدم موجود مسبقاً")
            return

        user = User(
            email=email,
            role=role,
            is_active=True
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

    await update.message.reply_text(f"✅ تم إنشاء المستخدم: {email}")


@admin_only
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with app.app_context():
        users = User.query.all()

    text = "📋 المستخدمون:\n\n"
    for u in users:
        status = "🟢 نشط" if u.is_active else "🔴 معطل"
        text += f"{u.email} | {u.role} | {status}\n"

    await update.message.reply_text(text)


@admin_only
async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.args[0]

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return

        user.is_active = True
        db.session.commit()

    await update.message.reply_text("✅ تم تفعيل المستخدم")


@admin_only
async def deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.args[0]

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return

        user.is_active = False
        db.session.commit()

    await update.message.reply_text("⛔ تم تعطيل المستخدم")


@admin_only
async def reset_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        email, new_password = context.args
    except ValueError:
        await update.message.reply_text("❌ الاستخدام:\n/reset_password email new_password")
        return

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return

        user.set_password(new_password)
        db.session.commit()

    await update.message.reply_text("🔑 تم تغيير كلمة المرور")


def main():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("add_user", add_user))
    app_bot.add_handler(CommandHandler("list_users", list_users))
    app_bot.add_handler(CommandHandler("activate", activate))
    app_bot.add_handler(CommandHandler("deactivate", deactivate))
    app_bot.add_handler(CommandHandler("reset_password", reset_password))

    print("🤖 Bot started...")
    app_bot.run_polling()


if __name__ == "__main__":
    main()
