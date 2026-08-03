import cron from 'node-cron';
import db from '../database/db.js';
import { sendMessage, sendBroadcast } from '../whatsapp/manager.js';
import { getBot } from '../telegram/bot.js';
import config from '../config/env.js';

// تخزين المهام المجدولة
const scheduledTasks = new Map();

// ====== تهيئة المجدول ======
export function initScheduler() {
    console.log('⏰ Initializing scheduler...');
    
    // تحميل المهام من قاعدة البيانات
    loadScheduledTasks();
    
    // تشغيل فحص كل دقيقة
    cron.schedule('* * * * *', () => {
        checkScheduledMessages();
    });
    
    console.log('✅ Scheduler started');
}

// ====== تحميل المهام المجدولة ======
function loadScheduledTasks() {
    const stmt = db.prepare(`
        SELECT * FROM scheduled_messages 
        WHERE status = 'pending' 
        AND scheduled_at <= datetime('now')
    `);
    
    const tasks = stmt.all();
    
    for (const task of tasks) {
        scheduledTasks.set(task.id, task);
    }
    
    console.log(`📋 Loaded ${tasks.length} scheduled tasks`);
}

// ====== فحص الرسائل المجدولة ======
async function checkScheduledMessages() {
    const now = new Date().toISOString();
    
    const stmt = db.prepare(`
        SELECT * FROM scheduled_messages 
        WHERE status = 'pending' 
        AND scheduled_at <= ?
    `);
    
    const tasks = stmt.all(now);
    
    for (const task of tasks) {
        await executeScheduledTask(task);
    }
}

// ====== تنفيذ مهمة مجدولة ======
async function executeScheduledTask(task) {
    console.log(`⏰ Executing scheduled task: ${task.id}`);
    
    try {
        let result;
        
        if (task.type === 'single') {
            // إرسال رسالة فردية
            result = await sendMessage(
                task.phone,
                task.recipient,
                task.message
            );
        } else if (task.type === 'broadcast') {
            // إرسال رسالة جماعية
            const recipients = JSON.parse(task.recipients);
            result = await sendBroadcast(
                task.phone,
                recipients,
                task.message
            );
        } else if (task.type === 'status') {
            // نشر حالة
            const { sendStatus } = await import('../whatsapp/manager.js');
            result = await sendStatus(
                task.phone,
                task.message,
                task.media_url || null
            );
        }
        
        // تحديث حالة المهمة
        const updateStmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = 'completed', 
                executed_at = CURRENT_TIMESTAMP,
                result = ?
            WHERE id = ?
        `);
        updateStmt.run(JSON.stringify(result), task.id);
        
        // إرسال إشعار
        const bot = getBot();
        if (bot) {
            const adminId = config.ADMIN_ID;
            const msg = `✅ تم تنفيذ المهمة المجدولة #${task.id}\n` +
                       `📱 حساب: ${task.phone}\n` +
                       `📝 نوع: ${task.type}\n` +
                       `📊 النتيجة: ${result.success || result.total || 'ناجحة'}`;
            bot.telegram.sendMessage(adminId, msg).catch(() => {});
        }
        
        scheduledTasks.delete(task.id);
        
    } catch (error) {
        console.error(`❌ Failed to execute task ${task.id}:`, error);
        
        // تحديث حالة المهمة بالفشل
        const updateStmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = 'failed', 
                error = ?
            WHERE id = ?
        `);
        updateStmt.run(error.message, task.id);
    }
}

// ====== إضافة مهمة مجدولة ======
export function addScheduledTask({
    phone,
    type, // 'single', 'broadcast', 'status'
    recipient = null,
    recipients = null,
    message,
    media_url = null,
    scheduled_at,
    repeat = null // 'daily', 'weekly', 'monthly'
}) {
    const stmt = db.prepare(`
        INSERT INTO scheduled_messages (
            phone, type, recipient, recipients, message, 
            media_url, scheduled_at, repeat, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    `);
    
    const info = stmt.run(
        phone,
        type,
        recipient,
        recipients ? JSON.stringify(recipients) : null,
        message,
        media_url,
        scheduled_at,
        repeat
    );
    
    // إضافة للمهام النشطة
    const task = {
        id: info.lastInsertRowid,
        phone,
        type,
        recipient,
        recipients,
        message,
        media_url,
        scheduled_at,
        repeat,
        status: 'pending'
    };
    scheduledTasks.set(info.lastInsertRowid, task);
    
    return info.lastInsertRowid;
}

// ====== إلغاء مهمة مجدولة ======
export function cancelScheduledTask(taskId) {
    const stmt = db.prepare(`
        UPDATE scheduled_messages 
        SET status = 'cancelled' 
        WHERE id = ?
    `);
    stmt.run(taskId);
    scheduledTasks.delete(taskId);
    return true;
}

// ====== الحصول على المهام المجدولة ======
export function getScheduledTasks(status = null) {
    let query = `SELECT * FROM scheduled_messages`;
    const params = [];
    
    if (status) {
        query += ` WHERE status = ?`;
        params.push(status);
    }
    
    query += ` ORDER BY scheduled_at ASC`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== تحديث مهمة مجدولة ======
export function updateScheduledTask(taskId, updates) {
    const fields = [];
    const values = [];
    
    for (const [key, value] of Object.entries(updates)) {
        fields.push(`${key} = ?`);
        values.push(value);
    }
    
    values.push(taskId);
    
    const stmt = db.prepare(`
        UPDATE scheduled_messages 
        SET ${fields.join(', ')} 
        WHERE id = ?
    `);
    
    stmt.run(...values);
    
    // تحديث في الذاكرة
    if (scheduledTasks.has(taskId)) {
        const task = scheduledTasks.get(taskId);
        Object.assign(task, updates);
        scheduledTasks.set(taskId, task);
    }
    
    return true;
}

// ====== جدولة رسالة متكررة ======
export function scheduleRecurring({
    phone,
    type,
    recipient = null,
    recipients = null,
    message,
    media_url = null,
    start_date,
    repeat, // 'daily', 'weekly', 'monthly'
    end_date = null
}) {
    const stmt = db.prepare(`
        INSERT INTO scheduled_messages (
            phone, type, recipient, recipients, message,
            media_url, scheduled_at, repeat, end_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'recurring')
    `);
    
    const info = stmt.run(
        phone,
        type,
        recipient,
        recipients ? JSON.stringify(recipients) : null,
        message,
        media_url,
        start_date,
        repeat,
        end_date
    );
    
    // جدولة المهمة المتكررة
    scheduleRecurringTask(info.lastInsertRowid);
    
    return info.lastInsertRowid;
}

// ====== جدولة مهمة متكررة ======
function scheduleRecurringTask(taskId) {
    const task = getScheduledTasks().find(t => t.id === taskId);
    if (!task) return;
    
    // حساب الموعد التالي
    const nextDate = calculateNextDate(
        task.scheduled_at,
        task.repeat
    );
    
    if (task.end_date && new Date(nextDate) > new Date(task.end_date)) {
        // انتهت المهمة
        const stmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = 'completed' 
            WHERE id = ?
        `);
        stmt.run(taskId);
        return;
    }
    
    // إنشاء نسخة جديدة للموعد القادم
    const newTask = {
        ...task,
        scheduled_at: nextDate,
        status: 'pending'
    };
    delete newTask.id;
    
    addScheduledTask(newTask);
}

// ====== حساب الموعد التالي ======
function calculateNextDate(date, repeat) {
    const next = new Date(date);
    
    switch (repeat) {
        case 'daily':
            next.setDate(next.getDate() + 1);
            break;
        case 'weekly':
            next.setDate(next.getDate() + 7);
            break;
        case 'monthly':
            next.setMonth(next.getMonth() + 1);
            break;
        default:
            return date;
    }
    
    return next.toISOString();
}

export default {
    initScheduler,
    addScheduledTask,
    cancelScheduledTask,
    getScheduledTasks,
    updateScheduledTask,
    scheduleRecurring
};
