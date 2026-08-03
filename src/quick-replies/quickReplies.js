import db from "../database/db.js";

// تخزين الردود السريعة
const quickReplies = new Map();

// ====== إضافة رد سريع ======
export function addQuickReply(phone, keyword, reply, mediaPath = null) {
    const replyId = `qr_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    const stmt = db.prepare(`
        INSERT INTO quick_replies (reply_id, phone, keyword, reply_text, media_path)
        VALUES (?, ?, ?, ?, ?)
    `);
    stmt.run(replyId, phone, keyword.toLowerCase(), reply, mediaPath);
    
    // تحديث الذاكرة
    if (!quickReplies.has(phone)) {
        quickReplies.set(phone, []);
    }
    quickReplies.get(phone).push({ 
        id: replyId, 
        keyword: keyword.toLowerCase(), 
        reply, 
        mediaPath 
    });
    
    return { success: true, replyId };
}

// ====== حذف رد سريع ======
export function deleteQuickReply(replyId) {
    const stmt = db.prepare(`DELETE FROM quick_replies WHERE reply_id = ?`);
    stmt.run(replyId);
    
    // حذف من الذاكرة
    for (const [phone, replies] of quickReplies) {
        const index = replies.findIndex(r => r.id === replyId);
        if (index !== -1) {
            replies.splice(index, 1);
            break;
        }
    }
    
    return { success: true };
}

// ====== معالجة رد سريع ======
export async function processQuickReply(phone, sender, message, sock) {
    const replies = quickReplies.get(phone) || [];
    const msgLower = message.toLowerCase();
    
    for (const reply of replies) {
        if (msgLower === reply.keyword || msgLower.startsWith(reply.keyword + ' ')) {
            try {
                if (reply.mediaPath) {
                    // إرسال مع ميديا
                    await sock.sendMessage(sender, {
                        image: { url: reply.mediaPath },
                        caption: reply.reply
                    });
                } else {
                    await sock.sendMessage(sender, { text: reply.reply });
                }
                
                // تسجيل الاستخدام
                const logStmt = db.prepare(`
                    INSERT INTO quick_reply_logs (phone, reply_id, sender, trigger_message)
                    VALUES (?, ?, ?, ?)
                `);
                logStmt.run(phone, reply.id, sender, message);
                
                return { used: true, reply: reply.reply };
            } catch (error) {
                console.error(`❌ Failed to send quick reply:`, error);
                return { used: false, error: error.message };
            }
        }
    }
    
    return { used: false };
}

// ====== الحصول على الردود السريعة ======
export function getQuickReplies(phone) {
    const stmt = db.prepare(`
        SELECT * FROM quick_replies WHERE phone = ?
    `);
    return stmt.all(phone);
}

export default {
    addQuickReply,
    deleteQuickReply,
    processQuickReply,
    getQuickReplies
};
