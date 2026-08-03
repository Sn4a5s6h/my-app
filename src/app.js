import express from "express";
import config from "./config/env.js";
import "./database/db.js";
import { startBot } from "./telegram/bot.js";
import webApp from "./web/server.js";
import { restoreScheduledMessages } from "./scheduler/scheduler.js";
import { startAutoBackup } from "./backup/backup.js";

const app = express();

// استخدام تطبيق الويب
app.use(webApp);

// استعادة المهام المجدولة
restoreScheduledMessages();

// بدء النسخ الاحتياطي التلقائي (كل 24 ساعة)
startAutoBackup(24);

// بدء الخادم
const server = app.listen(config.PORT, () => {
    console.log(`✅ Server running on port ${config.PORT}`);
    console.log(`🌐 Web Panel: http://localhost:${config.PORT}`);
    console.log(`🤖 Telegram Bot: @${config.TELEGRAM_TOKEN ? 'Active' : 'Missing Token'}`);
    console.log(`📅 Scheduler: Active`);
    console.log(`💾 Auto-Backup: Active (every 24 hours)`);
});

// بدء بوت التيليجرام
startBot();

// معالجة إغلاق الخادم
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down...');
    server.close(() => {
        console.log('✅ Server closed');
        process.exit(0);
    });
}); 
