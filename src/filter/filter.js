import db from "../database/db.js";

// تخزين الكلمات الممنوعة
const bannedWords = new Map();

// ====== إضافة كلمة ممنوعة ======
export function addBannedWord(phone, word, action = 'delete') {
    const wordId = `bw_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    const stmt = db.prepare(`
        INSERT INTO banned_words (word_id, phone, word, action)
        VALUES (?, ?, ?, ?)
    `);
    stmt.run(wordId, phone, word.toLowerCase(), action);
    
    // تحديث الذاكرة
    if (!bannedWords.has(phone)) {
        bannedWords.set(phone, []);
    }
    bannedWords.get(phone).push({ id: wordId, word: word.toLowerCase(), action });
    
    return { success: true, wordId, word };
}

// ====== حذف كلمة ممنوعة ======
export function removeBannedWord(wordId) {
    const stmt = db.prepare(`DELETE FROM banned_words WHERE word_id = ?`);
    stmt.run(wordId);
    
    // حذف من الذاكرة
    for (const [phone, words] of bannedWords) {
        const index = words.findIndex(w => w.id === wordId);
        if (index !== -1) {
            words.splice(index, 1);
            break;
        }
    }
    
    return { success: true };
}

// ====== فحص الرسالة ======
export function checkMessage(phone, message) {
    const words = bannedWords.get(phone) || [];
    const msgLower = message.toLowerCase();
    
    for (const banned of words) {
        if (msgLower.includes(banned.word)) {
            return {
                blocked: true,
                word: banned.word,
                action: banned.action
            };
        }
    }
    
    return { blocked: false };
}

// ====== الحصول على الكلمات الممنوعة ======
export function getBannedWords(phone) {
    const stmt = db.prepare(`
        SELECT * FROM banned_words WHERE phone = ?
    `);
    return stmt.all(phone);
}

// ====== معالجة رسالة واردة ======
export async function processFilter(phone, sender, message, sock) {
    const result = checkMessage(phone, message);
    
    if (result.blocked) {
        if (result.action === 'delete') {
            // حذف الرسالة (محاكاة)
            console.log(`🗑️ Blocked message from ${sender}: "${message}" - contains "${result.word}"`);
            
            // إرسال تحذير للمرسل (اختياري)
            // await sock.sendMessage(sender, { text: "⚠️ رسالتك تحتوي على كلمات ممنوعة" });
            
            return { blocked: true, action: 'delete' };
        } else if (result.action === 'warn') {
            // إرسال تحذير
            await sock.sendMessage(sender, { 
                text: `⚠️ تنبيه: رسالتك تحتوي على كلمة ممنوعة ("${result.word}")` 
            });
            return { blocked: true, action: 'warn' };
        }
    }
    
    return { blocked: false };
}

export default {
    addBannedWord,
    removeBannedWord,
    checkMessage,
    getBannedWords,
    processFilter
};
