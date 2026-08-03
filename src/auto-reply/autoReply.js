import db from "../database/db.js";
import { sendMessage } from "../whatsapp/manager.js";

// تخزين قواعد الردود التلقائية
const autoReplyRules = new Map();

// ====== إضافة قاعدة رد تلقائي ======
export function addAutoReplyRule({
    phone,
    trigger,
    reply,
    matchType = 'contains', // 'contains', 'exact', 'starts_with', 'regex'
    active = true,
    mediaPath = null
}) {
    const ruleId = `rule_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    const rule = {
        id: ruleId,
        phone,
        trigger,
        reply,
        matchType,
        active,
        mediaPath,
        created_at: new Date().toISOString()
    };
    
    // حفظ في قاعدة البيانات
    const stmt = db.prepare(`
        INSERT INTO auto_reply_rules (
            rule_id, phone, trigger_text, reply_text, 
            match_type, active, media_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
        ruleId,
        phone,
        trigger,
        reply,
        matchType,
        active ? 1 : 0,
        mediaPath
    );
    
    // حفظ في الذاكرة
    if (!autoReplyRules.has(phone)) {
        autoReplyRules.set(phone, []);
    }
    autoReplyRules.get(phone).push(rule);
    
    return rule;
}

// ====== معالجة رسالة واردة ======
export async function processAutoReply(phone, sender, message, sock) {
    const rules = autoReplyRules.get(phone) || [];
    
    // جلب القواعد من قاعدة البيانات إذا لم تكن في الذاكرة
    if (rules.length === 0) {
        const stmt = db.prepare(`
            SELECT * FROM auto_reply_rules 
            WHERE phone = ? AND active = 1
        `);
        const dbRules = stmt.all(phone);
        autoReplyRules.set(phone, dbRules);
    }
    
    const activeRules = autoReplyRules.get(phone) || [];
    
    for (const rule of activeRules) {
        if (!rule.active) continue;
        
        let matched = false;
        const msgText = message.toLowerCase();
        const triggerText = rule.trigger_text.toLowerCase();
        
        switch (rule.match_type) {
            case 'contains':
                matched = msgText.includes(triggerText);
                break;
            case 'exact':
                matched = msgText === triggerText;
                break;
            case 'starts_with':
                matched = msgText.startsWith(triggerText);
                break;
            case 'regex':
                try {
                    const regex = new RegExp(triggerText, 'i');
                    matched = regex.test(message);
                } catch (e) {
                    matched = false;
                }
                break;
        }
        
        if (matched) {
            try {
                // إرسال الرد
                if (rule.media_path) {
                    // إرسال مع ميديا
                    await sock.sendMessage(sender, {
                        image: { url: rule.media_path },
                        caption: rule.reply_text
                    });
                } else {
                    await sendMessage(phone, sender, rule.reply_text);
                }
                
                // تسجيل الرد
                const logStmt = db.prepare(`
                    INSERT INTO auto_reply_logs (
                        phone, rule_id, sender, trigger_message, reply_message
                    ) VALUES (?, ?, ?, ?, ?)
                `);
                logStmt.run(
                    phone,
                    rule.id,
                    sender,
                    message,
                    rule.reply_text
                );
                
                console.log(`✅ Auto-reply sent to ${sender} using rule ${rule.id}`);
                
                // إيقاف البحث بعد أول تطابق
                break;
                
            } catch (error) {
                console.error(`❌ Failed to send auto-reply:`, error);
            }
        }
    }
}

// ====== حذف قاعدة ======
export function deleteAutoReplyRule(ruleId) {
    const stmt = db.prepare(`DELETE FROM auto_reply_rules WHERE rule_id = ?`);
    stmt.run(ruleId);
    
    // حذف من الذاكرة
    for (const [phone, rules] of autoReplyRules) {
        const index = rules.findIndex(r => r.id === ruleId);
        if (index !== -1) {
            rules.splice(index, 1);
            break;
        }
    }
    
    return { success: true, message: "تم حذف القاعدة" };
}

// ====== الحصول على جميع القواعد ======
export function getAutoReplyRules(phone = null) {
    let query = `SELECT * FROM auto_reply_rules`;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY created_at DESC`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== تحديث حالة القاعدة ======
export function toggleAutoReplyRule(ruleId, active) {
    const stmt = db.prepare(`
        UPDATE auto_reply_rules SET active = ? WHERE rule_id = ?
    `);
    stmt.run(active ? 1 : 0, ruleId);
    
    // تحديث في الذاكرة
    for (const [phone, rules] of autoReplyRules) {
        const rule = rules.find(r => r.id === ruleId);
        if (rule) {
            rule.active = active;
            break;
        }
    }
    
    return { success: true, message: `تم ${active ? 'تفعيل' : 'تعطيل'} القاعدة` };
}

export default {
    addAutoReplyRule,
    processAutoReply,
    deleteAutoReplyRule,
    getAutoReplyRules,
    toggleAutoReplyRule
};
