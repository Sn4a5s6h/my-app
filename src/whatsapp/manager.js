// إضافة في بداية الملف بعد الـ imports
import { handleAutoReply } from '../auto-reply/rules.js';
import { getBot } from '../telegram/bot.js';

// تحديث دالة handleIncomingMessage
async function handleIncomingMessage(phone, message, sock) {
    console.log(`📨 ${phone} - رسالة جديدة:`, message);
    
    const db = (await import("../database/db.js")).default;
    const sender = message.key.remoteJid;
    const receiver = phone + "@s.whatsapp.net";
    
    // استخراج محتوى الرسالة (نفس الكود السابق)
    let text = "";
    let mediaType = null;
    let mediaUrl = null;

    if (message.message) {
        const msg = message.message;
        
        if (msg.conversation) {
            text = msg.conversation;
        } else if (msg.extendedTextMessage?.text) {
            text = msg.extendedTextMessage.text;
        } else if (msg.imageMessage) {
            text = "🖼️ صورة";
            mediaType = "image";
            mediaUrl = await downloadMedia(message, sock);
        } else if (msg.videoMessage) {
            text = "🎥 فيديو";
            mediaType = "video";
            mediaUrl = await downloadMedia(message, sock);
        } else if (msg.audioMessage) {
            text = "🎵 صوت";
            mediaType = "audio";
        } else if (msg.documentMessage) {
            text = `📄 مستند: ${msg.documentMessage.fileName || 'ملف'}`;
            mediaType = "document";
        } else if (msg.stickerMessage) {
            text = "🧩 ملصق";
            mediaType = "sticker";
        } else if (msg.contactMessage) {
            text = `👤 جهة اتصال: ${msg.contactMessage.displayName}`;
        } else if (msg.locationMessage) {
            text = `📍 موقع: ${msg.locationMessage.degreesLatitude}, ${msg.locationMessage.degreesLongitude}`;
        } else {
            text = "📎 وسائط";
        }
    }

    // حفظ الرسالة
    const stmt = db.prepare(`
        INSERT INTO messages (phone, direction, sender, receiver, message, media_type, media_url, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(phone, "incoming", sender, receiver, text, mediaType, mediaUrl, "received");

    // ====== معالجة الردود التلقائية ======
    if (text && !message.key.fromMe) {
        await handleAutoReply(phone, text, sender);
    }

    // إرسال إشعار إلى التيليجرام (مع إمكانية التعطيل)
    const bot = getBot();
    if (bot) {
        const adminId = (await import("../config/env.js")).default.ADMIN_ID;
        const msg = `📩 رسالة جديدة\n📱 حساب: ${phone}\n👤 من: ${sender}\n💬 ${text}`;
        bot.telegram.sendMessage(adminId, msg).catch(() => {});
    }
}
