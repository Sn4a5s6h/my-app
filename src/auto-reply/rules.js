// src/auto-reply/rules.js
// نظام الرد التلقائي المتقدم

import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ==================== قاعدة البيانات المحلية للردود ====================

// تخزين الردود في الذاكرة (يمكن استبدالها بقاعدة بيانات)
const replyRules = new Map();

// الردود الافتراضية
const defaultRules = [
    // ردود الترحيب
    {
        id: 'welcome_1',
        keywords: ['مرحباً', 'مرحبا', 'اهلاً', 'اهلا', 'هلا', 'السلام عليكم', 'سلام'],
        reply: '🌹 مرحباً بك! كيف يمكنني مساعدتك اليوم؟',
        priority: 1,
        enabled: true
    },
    {
        id: 'welcome_2',
        keywords: ['صباح الخير', 'صباح النور', 'مساء الخير', 'مساء النور'],
        reply: '☀️ صباح النور والسرور! كيف يمكنني خدمتك؟',
        priority: 1,
        enabled: true
    },
    
    // ردود الشكر
    {
        id: 'thanks_1',
        keywords: ['شكراً', 'شكرا', 'مشكور', 'يعطيك العافية', 'بارك الله فيك'],
        reply: '🤗 العفو، بكل سرور! هل هناك شيء آخر تحتاجه؟',
        priority: 2,
        enabled: true
    },
    
    // ردود الوداع
    {
        id: 'goodbye_1',
        keywords: ['مع السلامة', 'الى اللقاء', 'وداعاً', 'باي', 'bye'],
        reply: '👋 مع السلامة، ننتظر عودتك!',
        priority: 1,
        enabled: true
    },
    
    // ردود الأسئلة الشائعة
    {
        id: 'faq_1',
        keywords: ['الخدمات', 'خدمات', 'ماذا تقدم', 'ما هي خدماتكم'],
        reply: '📋 خدماتنا تشمل:\n• إدارة حسابات واتساب\n• إرسال رسائل جماعية\n• نشر حالات\n• ردود تلقائية ذكية\n• تقارير وتحليلات',
        priority: 3,
        enabled: true
    },
    {
        id: 'faq_2',
        keywords: ['السعر', 'التكلفة', 'بكم', 'كم سعر', 'أسعار'],
        reply: '💰 للاستفسار عن الأسعار والخطط، يرجى التواصل مع الإدارة عبر البوت.',
        priority: 3,
        enabled: true
    },
    {
        id: 'faq_3',
        keywords: ['وقت', 'متى', 'مدة', 'الوقت'],
        reply: '⏰ أوقات العمل: من 9 صباحاً إلى 10 مساءً بتوقيت مكة المكرمة.',
        priority: 3,
        enabled: true
    },
    
    // ردود الدعم الفني
    {
        id: 'support_1',
        keywords: ['مشكلة', 'خطأ', 'لا يعمل', 'عطل', 'مساعدة', 'دعم'],
        reply: '🛠️ جاري التواصل مع فريق الدعم الفني لحل مشكلتك في أقرب وقت.',
        priority: 4,
        enabled: true
    },
    {
        id: 'support_2',
        keywords: ['ابلغ', 'شكوى', 'اقتراح', 'تطوير'],
        reply: '📝 تم تسجيل ملاحظاتك وسيتم دراستها من قبل فريق التطوير.',
        priority: 4,
        enabled: true
    },
    
    // ردود ترويجية
    {
        id: 'promo_1',
        keywords: ['عرض', 'خصم', 'تخفيض', 'كود خصم', 'كوبون'],
        reply: '🎉 احصل على خصم 20% عند الاشتراك السنوي! استخدم الكود: SAVE20',
        priority: 5,
        enabled: true
    },
    
    // ردود للمزاح
    {
        id: 'fun_1',
        keywords: ['كيف الحال', 'اخبارك', 'شو اخبارك', 'كيفك'],
        reply: '😊 الحمد لله، بخير! شكراً لسؤالك، كيف أستطيع مساعدتك؟',
        priority: 1,
        enabled: true
    },
    {
        id: 'fun_2',
        keywords: ['وناسة', 'تسلية', 'نكتة', 'ضحك', 'مزاح'],
        reply: '😄 لماذا لا يضحك الكمبيوتر؟ لأنه لا يفهم النكتة! 😅\nهل تريد نكتة أخرى؟',
        priority: 5,
        enabled: true
    }
];

// ==================== تحميل الردود ====================

/**
 * تحميل الردود من ملف أو استخدام الافتراضية
 */
function loadRules() {
    try {
        // محاولة تحميل الردود من ملف JSON
        const rulesPath = path.join(__dirname, 'rules.json');
        if (fs.existsSync(rulesPath)) {
            const data = fs.readFileSync(rulesPath, 'utf8');
            const rules = JSON.parse(data);
            rules.forEach(rule => {
                replyRules.set(rule.id, rule);
            });
            console.log(`✅ تم تحميل ${rules.length} رد تلقائي من الملف`);
            return;
        }
    } catch (error) {
        console.warn('⚠️ لم يتم العثور على ملف rules.json، استخدام الردود الافتراضية');
    }
    
    // استخدام الردود الافتراضية
    defaultRules.forEach(rule => {
        replyRules.set(rule.id, rule);
    });
    console.log(`✅ تم تحميل ${defaultRules.length} رد تلقائي افتراضي`);
}

// تحميل الردود عند بدء التشغيل
loadRules();

// ==================== وظائف البحث عن الردود ====================

/**
 * البحث عن رد مناسب بناءً على النص
 * @param {string} text - النص المراد البحث عنه
 * @returns {Object|null} - الرد المناسب
 */
function findMatchingReply(text) {
    if (!text) return null;
    
    const normalizedText = text.toLowerCase().trim();
    let bestMatch = null;
    let highestPriority = Infinity;
    
    for (const [id, rule] of replyRules) {
        if (!rule.enabled) continue;
        
        for (const keyword of rule.keywords) {
            if (normalizedText.includes(keyword.toLowerCase())) {
                // اختيار الرد ذو الأولوية الأعلى (رقم أقل = أولوية أعلى)
                if (rule.priority < highestPriority) {
                    highestPriority = rule.priority;
                    bestMatch = rule;
                }
                break;
            }
        }
    }
    
    return bestMatch;
}

/**
 * البحث عن ردود متعددة تطابق النص
 * @param {string} text - النص المراد البحث عنه
 * @returns {Array} - قائمة الردود المطابقة
 */
function findMatchingReplies(text) {
    if (!text) return [];
    
    const normalizedText = text.toLowerCase().trim();
    const matches = [];
    
    for (const [id, rule] of replyRules) {
        if (!rule.enabled) continue;
        
        for (const keyword of rule.keywords) {
            if (normalizedText.includes(keyword.toLowerCase())) {
                matches.push(rule);
                break;
            }
        }
    }
    
    // ترتيب حسب الأولوية
    return matches.sort((a, b) => a.priority - b.priority);
}

// ==================== معالجة الرد التلقائي ====================

/**
 * معالجة الرسالة والرد عليها تلقائياً
 * @param {string} phone - رقم حساب الواتساب
 * @param {Object} message - كائن الرسالة
 * @param {string} sender - رقم المرسل
 * @returns {Promise<boolean>} - نجاح أو فشل الرد
 */
export async function processAutoReply(phone, message, sender) {
    try {
        // استخراج النص من الرسالة
        let text = '';
        if (message.message) {
            const msg = message.message;
            if (msg.conversation) {
                text = msg.conversation;
            } else if (msg.extendedTextMessage?.text) {
                text = msg.extendedTextMessage.text;
            } else {
                // رسائل غير نصية (صور، فيديو، إلخ)
                return false;
            }
        }
        
        if (!text || text.length < 2) {
            return false; // تجاهل النصوص القصيرة جداً
        }
        
        // البحث عن رد مناسب
        const reply = findMatchingReply(text);
        if (!reply) {
            return false; // لا يوجد رد مناسب
        }
        
        // استيراد وظيفة الإرسال من manager
        const managerModule = await import('../whatsapp/manager.js');
        if (!managerModule.sendMessage) {
            console.error('❌ sendMessage function not found in manager');
            return false;
        }
        
        // إرسال الرد
        await managerModule.sendMessage(phone, sender, reply.reply);
        
        // تسجيل الرد في قاعدة البيانات (اختياري)
        try {
            const db = (await import('../database/db.js')).default;
            const stmt = db.prepare(`
                INSERT INTO auto_reply_logs (phone, sender, trigger_text, reply_text, rule_id, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            `);
            stmt.run(phone, sender, text, reply.reply, reply.id);
        } catch (dbError) {
            // تجاهل أخطاء قاعدة البيانات للردود التلقائية
        }
        
        console.log(`🤖 ${phone} - رد تلقائي: "${reply.reply}" (القاعدة: ${reply.id})`);
        return true;
        
    } catch (error) {
        console.error('❌ Auto-reply error:', error);
        return false;
    }
}

// ==================== إدارة الردود ====================

/**
 * إضافة رد تلقائي جديد
 * @param {Object} rule - كائن القاعدة
 * @returns {boolean} - نجاح الإضافة
 */
export function addReplyRule(rule) {
    try {
        if (!rule.id || !rule.keywords || !rule.reply) {
            throw new Error('القاعدة يجب أن تحتوي على id, keywords, reply');
        }
        
        replyRules.set(rule.id, {
            id: rule.id,
            keywords: Array.isArray(rule.keywords) ? rule.keywords : [rule.keywords],
            reply: rule.reply,
            priority: rule.priority || 1,
            enabled: rule.enabled !== undefined ? rule.enabled : true
        });
        
        // حفظ في ملف JSON
        saveRulesToFile();
        
        return true;
    } catch (error) {
        console.error('❌ Failed to add reply rule:', error);
        return false;
    }
}

/**
 * حذف رد تلقائي
 * @param {string} ruleId - معرف القاعدة
 * @returns {boolean} - نجاح الحذف
 */
export function removeReplyRule(ruleId) {
    try {
        if (!replyRules.has(ruleId)) {
            throw new Error('القاعدة غير موجودة');
        }
        
        replyRules.delete(ruleId);
        
        // حفظ في ملف JSON
        saveRulesToFile();
        
        return true;
    } catch (error) {
        console.error('❌ Failed to remove reply rule:', error);
        return false;
    }
}

/**
 * تحديث رد تلقائي
 * @param {string} ruleId - معرف القاعدة
 * @param {Object} updates - التحديثات
 * @returns {boolean} - نجاح التحديث
 */
export function updateReplyRule(ruleId, updates) {
    try {
        if (!replyRules.has(ruleId)) {
            throw new Error('القاعدة غير موجودة');
        }
        
        const rule = replyRules.get(ruleId);
        Object.assign(rule, updates);
        replyRules.set(ruleId, rule);
        
        // حفظ في ملف JSON
        saveRulesToFile();
        
        return true;
    } catch (error) {
        console.error('❌ Failed to update reply rule:', error);
        return false;
    }
}

/**
 * الحصول على جميع الردود
 * @returns {Array} - قائمة الردود
 */
export function getAllReplyRules() {
    return Array.from(replyRules.values());
}

/**
 * الحصول على رد محدد
 * @param {string} ruleId - معرف القاعدة
 * @returns {Object|null} - كائن القاعدة
 */
export function getReplyRule(ruleId) {
    return replyRules.get(ruleId) || null;
}

/**
 * تمكين أو تعطيل رد
 * @param {string} ruleId - معرف القاعدة
 * @param {boolean} enabled - حالة التمكين
 * @returns {boolean} - نجاح العملية
 */
export function toggleReplyRule(ruleId, enabled) {
    try {
        if (!replyRules.has(ruleId)) {
            throw new Error('القاعدة غير موجودة');
        }
        
        const rule = replyRules.get(ruleId);
        rule.enabled = enabled;
        replyRules.set(ruleId, rule);
        
        // حفظ في ملف JSON
        saveRulesToFile();
        
        return true;
    } catch (error) {
        console.error('❌ Failed to toggle reply rule:', error);
        return false;
    }
}

// ==================== حفظ الردود في ملف ====================

/**
 * حفظ الردود في ملف JSON
 */
function saveRulesToFile() {
    try {
        const rulesPath = path.join(__dirname, 'rules.json');
        const rules = Array.from(replyRules.values());
        fs.writeFileSync(rulesPath, JSON.stringify(rules, null, 2), 'utf8');
        console.log(`✅ تم حفظ ${rules.length} رد تلقائي في الملف`);
    } catch (error) {
        console.error('❌ Failed to save rules to file:', error);
    }
}

// ==================== واجهة برمجة التطبيقات (API) للبوت ====================

/**
 * معالجة أوامر الرد التلقائي من التيليجرام
 * @param {Object} ctx - سياق التيليجرام
 */
export async function handleAutoReplyCommands(ctx) {
    const command = ctx.message.text.split(' ')[0];
    const args = ctx.message.text.split(' ').slice(1);
    
    switch (command) {
        case '/rules_list':
            return await listRules(ctx);
        case '/rules_add':
            return await addRuleFromTelegram(ctx, args);
        case '/rules_remove':
            return await removeRuleFromTelegram(ctx, args);
        case '/rules_enable':
            return await toggleRuleFromTelegram(ctx, args, true);
        case '/rules_disable':
            return await toggleRuleFromTelegram(ctx, args, false);
        default:
            return false;
    }
}

/**
 * عرض قائمة الردود
 */
async function listRules(ctx) {
    const rules = getAllReplyRules();
    if (rules.length === 0) {
        return ctx.reply('📭 لا توجد ردود تلقائية');
    }
    
    let message = '📋 قائمة الردود التلقائية:\n\n';
    for (const rule of rules) {
        const status = rule.enabled ? '✅ مفعل' : '❌ معطل';
        message += `🆔 ${rule.id}\n`;
        message += `🔑 كلمات: ${rule.keywords.join(', ')}\n`;
        message += `💬 رد: ${rule.reply.substring(0, 50)}${rule.reply.length > 50 ? '...' : ''}\n`;
        message += `⭐ الأولوية: ${rule.priority}\n`;
        message += `📌 الحالة: ${status}\n\n`;
    }
    
    return ctx.reply(message);
}

/**
 * إضافة رد من التيليجرام
 */
async function addRuleFromTelegram(ctx, args) {
    try {
        if (args.length < 3) {
            return ctx.reply(
                '❌ استخدام: /rules_add [المعرف] [كلمات مفتاحية مفصولة بفاصلة] [الرد]\n' +
                'مثال: /rules_add greeting مرحبا,اهلا,سلام 🌹 مرحباً بك!'
            );
        }
        
        const id = args[0];
        const keywords = args[1].split(',').map(k => k.trim());
        const reply = args.slice(2).join(' ');
        
        const rule = {
            id,
            keywords,
            reply,
            priority: 1,
            enabled: true
        };
        
        if (addReplyRule(rule)) {
            return ctx.reply(`✅ تم إضافة الرد التلقائي "${id}" بنجاح`);
        } else {
            return ctx.reply('❌ فشل إضافة الرد، تأكد من أن المعرف غير مكرر');
        }
    } catch (error) {
        return ctx.reply(`❌ خطأ: ${error.message}`);
    }
}

/**
 * حذف رد من التيليجرام
 */
async function removeRuleFromTelegram(ctx, args) {
    try {
        if (args.length < 1) {
            return ctx.reply('❌ استخدام: /rules_remove [المعرف]');
        }
        
        const id = args[0];
        if (removeReplyRule(id)) {
            return ctx.reply(`✅ تم حذف الرد التلقائي "${id}"`);
        } else {
            return ctx.reply(`❌ لم يتم العثور على الرد "${id}"`);
        }
    } catch (error) {
        return ctx.reply(`❌ خطأ: ${error.message}`);
    }
}

/**
 * تمكين/تعطيل رد من التيليجرام
 */
async function toggleRuleFromTelegram(ctx, args, enabled) {
    try {
        if (args.length < 1) {
            return ctx.reply('❌ استخدام: /rules_enable [المعرف]  أو /rules_disable [المعرف]');
        }
        
        const id = args[0];
        if (toggleReplyRule(id, enabled)) {
            const status = enabled ? 'مفعل' : 'معطل';
            return ctx.reply(`✅ تم ${status} الرد التلقائي "${id}"`);
        } else {
            return ctx.reply(`❌ لم يتم العثور على الرد "${id}"`);
        }
    } catch (error) {
        return ctx.reply(`❌ خطأ: ${error.message}`);
    }
}

// ==================== التصدير النهائي ====================

export default {
    processAutoReply,
    addReplyRule,
    removeReplyRule,
    updateReplyRule,
    getAllReplyRules,
    getReplyRule,
    toggleReplyRule,
    handleAutoReplyCommands,
    findMatchingReply,
    findMatchingReplies
}; 
