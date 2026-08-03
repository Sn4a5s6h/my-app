import db from '../database/db.js';
import { sendMessage } from '../whatsapp/manager.js';
import { getBot } from '../telegram/bot.js';
import config from '../config/env.js';

// ====== تهيئة نظام الردود التلقائية ======
export function initAutoReply() {
    console.log('🤖 Initializing auto-reply system...');
    console.log('✅ Auto-reply system ready');
}

// ====== معالجة الرسالة للردود التلقائية ======
export async function handleAutoReply(phone, message, sender) {
    // جلب قواعد الردود
    const rules = getReplyRules(phone);
    
    for (const rule of rules) {
        if (matchesRule(message, rule)) {
            await executeReply(phone, sender, rule);
            break; // تنفيذ أول قاعدة متطابقة فقط
        }
    }
}

// ====== التحقق من تطابق القاعدة ======
function matchesRule(message, rule) {
    if (!message || !rule.trigger) return false;
    
    const msgText = message.toLowerCase();
    const trigger = rule.trigger.toLowerCase();
    
    switch (rule.match_type) {
        case 'exact':
            return msgText === trigger;
        case 'contains':
            return msgText.includes(trigger);
        case 'starts':
            return msgText.startsWith(trigger);
        case 'ends':
            return msgText.endsWith(trigger);
        case 'regex':
            try {
                const regex = new RegExp(rule.trigger, 'i');
                return regex.test(message);
            } catch {
                return false;
            }
        default:
            return msgText.includes(trigger);
    }
}

// ====== تنفيذ الرد ======
async function executeReply(phone, sender, rule) {
    try {
        let replyMessage = rule.reply;
        
        // دعم المتغيرات
        replyMessage = replyMessage
            .replace('{sender}', sender)
            .replace('{phone}', phone)
            .replace('{time}', new Date().toLocaleString());
        
        // إرسال الرد
        await sendMessage(phone, sender, replyMessage);
        
        // تسجيل الرد
        const stmt = db.prepare(`
            INSERT INTO auto_reply_logs (phone, sender, trigger, reply, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        `);
        stmt.run(phone, sender, rule.trigger, replyMessage);
        
        console.log(`🤖 Auto-reply sent to ${sender}: ${replyMessage}`);
        
    } catch (error) {
        console.error('❌ Failed to send auto-reply:', error);
    }
}

// ====== إضافة قاعدة رد جديد ======
export function addReplyRule({
    phone,
    trigger,
    reply,
    match_type = 'contains',
    enabled = true
}) {
    const stmt = db.prepare(`
        INSERT INTO auto_reply_rules (phone, trigger, reply, match_type, enabled)
        VALUES (?, ?, ?, ?, ?)
    `);
    
    const info = stmt.run(phone, trigger, reply, match_type, enabled ? 1 : 0);
    
    return info.lastInsertRowid;
}

// ====== الحصول على قواعد الردود ======
export function getReplyRules(phone = null) {
    let query = `SELECT * FROM auto_reply_rules WHERE enabled = 1`;
    const params = [];
    
    if (phone) {
        query += ` AND phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY priority DESC, id ASC`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== تحديث قاعدة رد ======
export function updateReplyRule(ruleId, updates) {
    const fields = [];
    const values = [];
    
    for (const [key, value] of Object.entries(updates)) {
        if (key === 'enabled') {
            fields.push(`${key} = ?`);
            values.push(value ? 1 : 0);
        } else {
            fields.push(`${key} = ?`);
            values.push(value);
        }
    }
    
    values.push(ruleId);
    
    const stmt = db.prepare(`
        UPDATE auto_reply_rules 
        SET ${fields.join(', ')} 
        WHERE id = ?
    `);
    
    stmt.run(...values);
    return true;
}

// ====== حذف قاعدة رد ======
export function deleteReplyRule(ruleId) {
    const stmt = db.prepare(`
        DELETE FROM auto_reply_rules WHERE id = ?
    `);
    stmt.run(ruleId);
    return true;
}

// ====== الحصول على سجل الردود ======
export function getReplyLogs(phone = null, limit = 50) {
    let query = `SELECT * FROM auto_reply_logs`;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY created_at DESC LIMIT ?`;
    params.push(limit);
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

export default {
    initAutoReply,
    handleAutoReply,
    addReplyRule,
    getReplyRules,
    updateReplyRule,
    deleteReplyRule,
    getReplyLogs
};
