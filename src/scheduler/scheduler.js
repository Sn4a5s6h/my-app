import schedule from "node-schedule";
import db from "../database/db.js";
import { sendMessage, sendBroadcast } from "../whatsapp/manager.js";
import { getBot } from "../telegram/bot.js";
import config from "../config/env.js";

// تخزين المهام المجدولة
const scheduledJobs = new Map();

// ====== جدولة رسالة ======
export function scheduleMessage({
    phone,
    to,
    message,
    mediaPath = null,
    scheduleTime, // Date object
    repeat = null, // 'daily', 'weekly', 'monthly'
    repeatInterval = null // عدد الدقائق
}) {
    const jobId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    let job;
    
    if (repeat === 'daily') {
        // جدولة يومية في نفس الوقت
        const [hours, minutes] = [
            scheduleTime.getHours(),
            scheduleTime.getMinutes()
        ];
        job = schedule.scheduleJob(`0 ${minutes} ${hours} * * *`, async () => {
            await executeScheduledMessage(phone, to, message, mediaPath, jobId);
        });
    } else if (repeat === 'weekly') {
        // جدولة أسبوعية
        const day = scheduleTime.getDay();
        const [hours, minutes] = [
            scheduleTime.getHours(),
            scheduleTime.getMinutes()
        ];
        job = schedule.scheduleJob(`0 ${minutes} ${hours} * * ${day}`, async () => {
            await executeScheduledMessage(phone, to, message, mediaPath, jobId);
        });
    } else if (repeatInterval) {
        // جدولة متكررة كل X دقيقة
        job = schedule.scheduleJob(`*/${repeatInterval} * * * *`, async () => {
            await executeScheduledMessage(phone, to, message, mediaPath, jobId);
        });
    } else {
        // جدولة لمرة واحدة
        job = schedule.scheduleJob(scheduleTime, async () => {
            await executeScheduledMessage(phone, to, message, mediaPath, jobId);
            // حذف المهمة بعد التنفيذ
            scheduledJobs.delete(jobId);
        });
    }
    
    // حفظ المهمة في قاعدة البيانات
    const stmt = db.prepare(`
        INSERT INTO scheduled_messages (
            job_id, phone, to_number, message, media_path, 
            schedule_time, repeat_type, repeat_interval, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
        jobId,
        phone,
        to,
        message,
        mediaPath,
        scheduleTime.toISOString(),
        repeat,
        repeatInterval,
        'scheduled'
    );
    
    scheduledJobs.set(jobId, job);
    
    return {
        jobId,
        scheduledTime: scheduleTime,
        message: "تم جدولة الرسالة بنجاح"
    };
}

// ====== تنفيذ رسالة مجدولة ======
async function executeScheduledMessage(phone, to, message, mediaPath, jobId) {
    try {
        let result;
        
        // إذا كان 'to' يحتوي على فاصلة، فهي رسالة جماعية
        if (to.includes(',')) {
            const numbers = to.split(',').map(n => n.trim());
            result = await sendBroadcast(phone, numbers, message, mediaPath);
        } else {
            result = await sendMessage(phone, to, message);
        }
        
        // تحديث حالة المهمة
        const stmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = ?, executed_at = CURRENT_TIMESTAMP, result = ?
            WHERE job_id = ?
        `);
        stmt.run('executed', JSON.stringify(result), jobId);
        
        // إرسال إشعار للمشرف
        const bot = getBot();
        if (bot) {
            const adminId = config.ADMIN_ID;
            bot.telegram.sendMessage(adminId, 
                `✅ تم تنفيذ الرسالة المجدولة ${jobId}\n📱 إلى: ${to}\n💬 ${message}`
            ).catch(() => {});
        }
        
        console.log(`✅ Executed scheduled message: ${jobId}`);
        
    } catch (error) {
        console.error(`❌ Failed to execute scheduled message ${jobId}:`, error);
        
        // تحديث حالة الفشل
        const stmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = ?, error = ?
            WHERE job_id = ?
        `);
        stmt.run('failed', error.message, jobId);
    }
}

// ====== إلغاء مهمة مجدولة ======
export function cancelScheduledMessage(jobId) {
    const job = scheduledJobs.get(jobId);
    if (job) {
        job.cancel();
        scheduledJobs.delete(jobId);
        
        // تحديث قاعدة البيانات
        const stmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = ? 
            WHERE job_id = ?
        `);
        stmt.run('cancelled', jobId);
        
        return { success: true, message: "تم إلغاء المهمة" };
    }
    throw new Error("المهمة غير موجودة");
}

// ====== الحصول على جميع المهام المجدولة ======
export function getScheduledMessages(phone = null) {
    let query = `SELECT * FROM scheduled_messages WHERE status = 'scheduled'`;
    const params = [];
    
    if (phone) {
        query += ` AND phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY schedule_time ASC`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== استعادة المهام عند تشغيل التطبيق ======
export function restoreScheduledMessages() {
    const stmt = db.prepare(`
        SELECT * FROM scheduled_messages 
        WHERE status = 'scheduled' 
        AND schedule_time > datetime('now')
    `);
    
    const messages = stmt.all();
    
    for (const msg of messages) {
        const scheduleTime = new Date(msg.schedule_time);
        if (scheduleTime > new Date()) {
            scheduleMessage({
                phone: msg.phone,
                to: msg.to_number,
                message: msg.message,
                mediaPath: msg.media_path,
                scheduleTime: scheduleTime,
                repeat: msg.repeat_type,
                repeatInterval: msg.repeat_interval
            });
        }
    }
    
    console.log(`🔄 Restored ${messages.length} scheduled messages`);
}

// ====== جدولة حالة (Status) ======
export function scheduleStatus({
    phone,
    message,
    mediaPath = null,
    scheduleTime,
    repeat = null
}) {
    const jobId = `status_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const job = schedule.scheduleJob(scheduleTime, async () => {
        try {
            const { sendStatus } = await import("../whatsapp/manager.js");
            await sendStatus(phone, message, mediaPath);
            
            // تحديث قاعدة البيانات
            const stmt = db.prepare(`
                UPDATE scheduled_statuses 
                SET status = ?, executed_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            `);
            stmt.run('executed', jobId);
            
            console.log(`✅ Scheduled status executed: ${jobId}`);
            
        } catch (error) {
            console.error(`❌ Failed to execute scheduled status:`, error);
        }
    });
    
    // حفظ في قاعدة البيانات
    const stmt = db.prepare(`
        INSERT INTO scheduled_statuses (
            job_id, phone, message, media_path, 
            schedule_time, repeat_type, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
        jobId,
        phone,
        message,
        mediaPath,
        scheduleTime.toISOString(),
        repeat,
        'scheduled'
    );
    
    scheduledJobs.set(jobId, job);
    
    return {
        jobId,
        scheduledTime: scheduleTime,
        message: "تم جدولة الحالة بنجاح"
    };
}

export default {
    scheduleMessage,
    cancelScheduledMessage,
    getScheduledMessages,
    restoreScheduledMessages,
    scheduleStatus
};
