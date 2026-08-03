import { Telegraf } from "telegraf";
import config from "../config/env.js";
import { 
    addAccount, 
    accounts, 
    getQR, 
    getAccountStatus,
    disconnectAccount,
    sendBroadcast,
    sendStatus,
    viewAllStatuses,
    getStatusViews
} from "../whatsapp/manager.js";

let bot = null;

// ✅ تصدير الدالة مباشرة
export function startBot() {
    try {
        if (!config.TELEGRAM_TOKEN) {
            console.error("❌ TELEGRAM_TOKEN not set in .env");
            return null;
        }

        bot = new Telegraf(config.TELEGRAM_TOKEN);

        // ====== أمر البداية ======
        bot.start(ctx => {
            ctx.reply(
                "🤖 WhatsApp Manager Online\n\n" +
                "📱 الأوامر المتاحة:\n" +
                "/start - عرض هذه الرسالة\n" +
                "/add_phone [رقم] - إضافة حساب جديد\n" +
                "/add_pairing [رقم] [كود] - إضافة حساب بكود الاقتران\n" +
                "/accounts - عرض الحسابات\n" +
                "/status [رقم] - حالة حساب\n" +
                "/send [رقم] [رسالة] - إرسال رسالة\n" +
                "/broadcast [رقم] [أرقام] [رسالة] - إرسال رسالة جماعية\n" +
                "/status_send [رقم] [رسالة] - نشر حالة\n" +
                "/status_view [رقم] - مشاهدة جميع الحالات\n" +
                "/disconnect [رقم] - قطع الاتصال\n" +
                "/help - عرض المساعدة"
            );
        });

        // ====== أمر المساعدة ======
        bot.command("help", ctx => {
            ctx.reply(
                "📖 الأوامر المتاحة:\n\n" +
                "🔹 /add_phone 966512345678 - إضافة حساب باستخدام QR\n" +
                "🔹 /add_pairing 966512345678 123456 - إضافة حساب بكود الاقتران\n" +
                "🔹 /accounts - عرض جميع الحسابات\n" +
                "🔹 /status 966512345678 - حالة حساب معين\n" +
                "🔹 /send 966512345678 نص الرسالة - إرسال رسالة\n" +
                "🔹 /broadcast 966512345678 أرقام مفصولة بفاصلة نص الرسالة\n" +
                "🔹 /status_send 966512345678 نص الحالة - نشر حالة\n" +
                "🔹 /status_view 966512345678 - مشاهدة كل الحالات\n" +
                "🔹 /disconnect 966512345678 - قطع الاتصال\n" +
                "🔹 /help - عرض هذه المساعدة"
            );
        });

        // ====== إضافة حساب بـ QR ======
        bot.command("add_phone", async ctx => {
            const phone = ctx.message.text.split(" ")[1];
            
            if (!phone) {
                return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /add_phone 966512345678");
            }

            await ctx.reply(`⏳ جاري إعداد حساب ${phone}...`);
            
            try {
                await addAccount(phone);
                
                setTimeout(async () => {
                    const qr = getQR(phone);
                    if (qr) {
                        await ctx.replyWithPhoto(
                            { source: Buffer.from(qr, 'base64') },
                            { caption: `📸 QR Code للحساب ${phone}\nامسح الكود باستخدام واتساب` }
                        );
                    } else {
                        await ctx.reply(`⚠️ لم يتم إنشاء QR بعد، انتظر قليلاً`);
                    }
                }, 3000);
                
            } catch (error) {
                await ctx.reply(`❌ خطأ: ${error.message}`);
            }
        });

        // ====== إضافة حساب بـ Pairing Code ======
        bot.command("add_pairing", async ctx => {
            const args = ctx.message.text.split(" ");
            const phone = args[1];
            const code = args[2];
            
            if (!phone) {
                return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /add_pairing 966512345678 123456");
            }

            if (!code) {
                return ctx.reply("❌ يرجى كتابة كود الاقتران (6 أرقام)");
            }

            await ctx.reply(`⏳ جاري الاقتران بالحساب ${phone}...`);
            
            try {
                await addAccount(phone, code);
                await ctx.reply(`✅ تم الاقتران بنجاح بالحساب ${phone}`);
            } catch (error) {
                await ctx.reply(`❌ فشل الاقتران: ${error.message}`);
            }
        });

        // ====== عرض الحسابات ======
        bot.command("accounts", async ctx => {
            const accs = accounts();
            
            if (accs.length === 0) {
                return ctx.reply("📭 لا يوجد حسابات نشطة");
            }

            let message = "📱 الحسابات النشطة:\n\n";
            for (const phone of accs) {
                const status = getAccountStatus(phone);
                const icon = status === "connected" ? "🟢" : status === "connecting" ? "🟡" : "🔴";
                message += `${icon} ${phone} - ${status}\n`;
            }
            
            await ctx.reply(message);
        });

        // ====== حالة حساب ======
        bot.command("status", async ctx => {
            const phone = ctx.message.text.split(" ")[1];
            
            if (!phone) {
                return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /status 966512345678");
            }

            const status = getAccountStatus(phone);
            const exists = accounts().includes(phone);
            
            if (!exists) {
                return ctx.reply(`❌ الحساب ${phone} غير موجود`);
            }

            const icon = status === "connected" ? "🟢" : status === "connecting" ? "🟡" : "🔴";
            await ctx.reply(`${icon} حالة الحساب ${phone}: ${status}`);
        });

        // ====== إرسال رسالة ======
        bot.command("send", async ctx => {
            const parts = ctx.message.text.split(" ");
            const phone = parts[1];
            const message = parts.slice(2).join(" ");
            
            if (!phone || !message) {
                return ctx.reply(
                    "❌ استخدام: /send [رقم الهاتف] [الرسالة]\n" +
                    "مثال: /send 966512345678 مرحبا كيف حالك؟"
                );
            }

            try {
                await ctx.reply(`⏳ جاري إرسال الرسالة إلى ${phone}...`);
                const { sendMessage } = await import("../whatsapp/manager.js");
                await sendMessage(phone, phone, message);
                await ctx.reply(`✅ تم إرسال الرسالة إلى ${phone}`);
            } catch (error) {
                await ctx.reply(`❌ فشل الإرسال: ${error.message}`);
            }
        });

        // ====== إرسال رسالة جماعية ======
        bot.command("broadcast", async ctx => {
            const args = ctx.message.text.split(" ");
            const phone = args[1];
            const numbersStr = args[2];
            const message = args.slice(3).join(" ");
            
            if (!phone || !numbersStr || !message) {
                return ctx.reply(
                    "❌ استخدام: /broadcast [رقم حسابك] [أرقام مفصولة بفاصلة] [الرسالة]\n" +
                    "مثال: /broadcast 966512345678 966511111111,966522222222,966533333333 مرحبا بالجميع"
                );
            }

            const numbers = numbersStr.split(",").map(n => n.trim());
            
            await ctx.reply(`⏳ جاري إرسال رسالة جماعية إلى ${numbers.length} شخص...`);
            
            try {
                const result = await sendBroadcast(phone, numbers, message);
                
                let reply = `📊 نتائج الإرسال الجماعي:\n`;
                reply += `✅ نجح: ${result.success}\n`;
                reply += `❌ فشل: ${result.failed}\n`;
                reply += `📝 المجموع: ${result.total}\n\n`;
                
                const results = result.results.slice(0, 5);
                for (const r of results) {
                    reply += `${r.success ? '✅' : '❌'} ${r.number}\n`;
                }
                if (result.results.length > 5) {
                    reply += `... و ${result.results.length - 5} أخرى`;
                }
                
                await ctx.reply(reply);
            } catch (error) {
                await ctx.reply(`❌ فشل الإرسال الجماعي: ${error.message}`);
            }
        });

        // ====== نشر حالة ======
        bot.command("status_send", async ctx => {
            const args = ctx.message.text.split(" ");
            const phone = args[1];
            const message = args.slice(2).join(" ");
            
            if (!phone || !message) {
                return ctx.reply(
                    "❌ استخدام: /status_send [رقم حسابك] [نص الحالة]\n" +
                    "مثال: /status_send 966512345678 مرحبا بالعالم"
                );
            }

            await ctx.reply(`⏳ جاري نشر الحالة...`);
            
            try {
                const result = await sendStatus(phone, message);
                await ctx.reply(`✅ ${result.message}\n🆔 ${result.statusId}`);
            } catch (error) {
                await ctx.reply(`❌ فشل نشر الحالة: ${error.message}`);
            }
        });

        // ====== مشاهدة جميع الحالات ======
        bot.command("status_view", async ctx => {
            const phone = ctx.message.text.split(" ")[1];
            
            if (!phone) {
                return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /status_view 966512345678");
            }

            await ctx.reply(`⏳ جاري مشاهدة جميع الحالات...`);
            
            try {
                const result = await viewAllStatuses(phone);
                
                let reply = `📊 نتائج مشاهدة الحالات:\n`;
                reply += `✅ تمت المشاهدة: ${result.viewed}\n`;
                reply += `📝 المجموع: ${result.total}\n\n`;
                
                const results = result.results.slice(0, 5);
                for (const r of results) {
                    reply += `${r.success ? '👁️' : '❌'} ${r.sender}\n`;
                }
                if (result.results.length > 5) {
                    reply += `... و ${result.results.length - 5} أخرى`;
                }
                
                await ctx.reply(reply);
            } catch (error) {
                await ctx.reply(`❌ فشل مشاهدة الحالات: ${error.message}`);
            }
        });

        // ====== قطع الاتصال ======
        bot.command("disconnect", async ctx => {
            const phone = ctx.message.text.split(" ")[1];
            
            if (!phone) {
                return ctx.reply("❌ يرجى كتابة رقم الهاتف\nمثال: /disconnect 966512345678");
            }

            try {
                await ctx.reply(`⏳ جاري قطع الاتصال بالحساب ${phone}...`);
                await disconnectAccount(phone);
                await ctx.reply(`✅ تم قطع الاتصال بالحساب ${phone}`);
            } catch (error) {
                await ctx.reply(`❌ فشل قطع الاتصال: ${error.message}`);
            }
        });

        // ====== معالجة الأخطاء ======
        bot.catch((err, ctx) => {
            console.error('❌ Bot error:', err);
            ctx.reply('⚠️ حدث خطأ، يرجى المحاولة لاحقاً').catch(() => {});
        });

        // ====== إطلاق البوت ======
        bot.launch()
            .then(() => {
                console.log("✅ Telegram bot started successfully");
            })
            .catch(err => {
                console.error("❌ Failed to launch bot:", err);
            });
        
        return bot;
        
    } catch (error) {
        console.error("❌ Error in startBot:", error);
        return null;
    }
}

// ✅ تصدير getBot
export function getBot() {
    return bot;
}
