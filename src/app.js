import express from "express";
import config from "./config/env.js";
import "./database/db.js";
import { startBot } from "./telegram/bot.js";

const app = express();

app.use(express.json());

// نقطة البداية
app.get("/", (req, res) => {
    res.send("WhatsApp Manager Running");
});

// تشغيل الخادم
const server = app.listen(config.PORT, () => {
    console.log(`✅ Server running on port ${config.PORT}`);
    console.log(`🌐 Web Panel: http://localhost:${config.PORT}`);
});

// تشغيل البوت مع معالجة الأخطاء
try {
    startBot();
    console.log("✅ Telegram bot initialized");
} catch (error) {
    console.error("❌ Telegram bot error:", error.message);
    console.log("⚠️ Running without Telegram bot");
}

// إيقاف التشغيل بشكل آمن
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down...');
    server.close(() => {
        console.log('✅ Server closed');
        process.exit(0);
    });
});

process.on('uncaughtException', (error) => {
    console.error('❌ Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('❌ Unhandled Rejection:', reason);
});
