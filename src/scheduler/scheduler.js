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
    try {
        const jobId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        let job;
        let cronExpression = null;

        // التحقق من صحة الوقت
        if (!(scheduleTime instanceof Date) || isNaN(scheduleTime.getTime())) {
            throw new Error("الوقت غير صحيح");
        }

        // إنشاء الجدولة بناءً على نوع التكرار
        if (repeat === 'daily') {
            const hours = scheduleTime.getHours();
            const minutes = scheduleTime.getMinutes();
            cronExpression = `${minutes} ${hours} * * *`;
            job = schedule.scheduleJob(cronExpression, async () => {
                await executeScheduledMessage(phone, to, message, mediaPath, jobId);
            });
        } else if (repeat === 'weekly') {
            const day = scheduleTime.getDay();
            const hours = scheduleTime.getHours();
            const minutes = scheduleTime.getMinutes();
            cronExpression = `${minutes} ${hours} * * ${day}`;
            job = schedule.scheduleJob(cronExpression, async () => {
                await executeScheduledMessage(phone, to, message, mediaPath, jobId);
            });
        } else if (repeatInterval) {
            cronExpression = `*/${repeatInterval} * * * *`;
            job = schedule.scheduleJob(cronExpression, async () => {
                await executeScheduledMessage(phone, to, message, mediaPath, jobId);
            });
        } else {
            // جدولة لمرة واحدة
            if (scheduleTime <= new Date()) {
                throw new Error("لا يمكن جدولة رسالة في الماضي");
            }
            job = schedule.scheduleJob(scheduleTime, async () => {
                await executeScheduledMessage(phone, to, message, mediaPath, jobId);
                scheduledJobs.delete(jobId);
            });
        }

        if (!job) {
            throw new Error("فشل إنشاء الجدولة");
        }

        // حفظ المهمة في قاعدة البيانات
        const stmt = db.prepare(`
            INSERT INTO scheduled_messages (
                job_id, phone, to_number, message, media_path, 
                schedule_time, repeat_type, repeat_interval, status, cron_expression
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            'scheduled',
            cronExpression
        );
        
        scheduledJobs.set(jobId, job);
        
        console.log(`✅ تم جدولة رسالة: ${jobId} في ${scheduleTime.toLocaleString()}`);
        
        return {
            success: true,
            jobId,
            scheduledTime: scheduleTime,
            cronExpression,
            message: "تم جدولة الرسالة بنجاح"
        };
        
    } catch (error) {
        console.error("❌ فشل جدولة الرسالة:", error);
        throw new Error(`فشل جدولة الرسالة: ${error.message}`);
    }
}

// ====== تنفيذ رسالة مجدولة ======
async function executeScheduledMessage(phone, to, message, mediaPath, jobId) {
    try {
        console.log(`⏰ تنفيذ رسالة مجدولة: ${jobId}`);
        
        // التحقق من وجود الحساب
        const accountStmt = db.prepare(`SELECT * FROM accounts WHERE phone = ?`);
        const account = accountStmt.get(phone);
        if (!account) {
            throw new Error(`الحساب ${phone} غير موجود`);
        }

        let result;
        
        // إذا كان 'to' يحتوي على فاصلة، فهي رسالة جماعية
        if (to.includes(',')) {
            const numbers = to.split(',').map(n => n.trim()).filter(n => n);
            if (numbers.length === 0) {
                throw new Error("لا توجد أرقام صالحة للإرسال");
            }
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
        if (bot && config.ADMIN_ID) {
            try {
                await bot.telegram.sendMessage(
                    config.ADMIN_ID,
                    `✅ تم تنفيذ الرسالة المجدولة\n📋 المعرف: ${jobId}\n📱 إلى: ${to}\n💬 ${message.substring(0, 100)}${message.length > 100 ? '...' : ''}`
                );
            } catch (telegramError) {
                console.warn("⚠️ فشل إرسال إشعار التيليجرام:", telegramError.message);
            }
        }
        
        console.log(`✅ تم تنفيذ الرسالة المجدولة: ${jobId}`);
        
    } catch (error) {
        console.error(`❌ فشل تنفيذ الرسالة المجدولة ${jobId}:`, error);
        
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
    try {
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
            
            console.log(`✅ تم إلغاء المهمة: ${jobId}`);
            return { success: true, message: "تم إلغاء المهمة" };
        }
        throw new Error("المهمة غير موجودة");
    } catch (error) {
        console.error("❌ فشل إلغاء المهمة:", error);
        throw new Error(`فشل إلغاء المهمة: ${error.message}`);
    }
}

// ====== الحصول على جميع المهام المجدولة ======
export function getScheduledMessages(phone = null) {
    try {
        let query = `SELECT * FROM scheduled_messages WHERE status = 'scheduled'`;
        const params = [];
        
        if (phone) {
            query += ` AND phone = ?`;
            params.push(phone);
        }
        
        query += ` ORDER BY schedule_time ASC`;
        
        const stmt = db.prepare(query);
        const results = stmt.all(...params);
        
        // إضافة معلومات إضافية
        return results.map(msg => ({
            ...msg,
            schedule_time_formatted: new Date(msg.schedule_time).toLocaleString(),
            is_past: new Date(msg.schedule_time) < new Date()
        }));
        
    } catch (error) {
        console.error("❌ فشل جلب المهام المجدولة:", error);
        return [];
    }
}

// ====== استعادة المهام عند تشغيل التطبيق ======
export function restoreScheduledMessages() {
    try {
        const stmt = db.prepare(`
            SELECT * FROM scheduled_messages 
            WHERE status = 'scheduled'
            ORDER BY schedule_time ASC
        `);
        
        const messages = stmt.all();
        let restoredCount = 0;
        
        for (const msg of messages) {
            try {
                const scheduleTime = new Date(msg.schedule_time);
                const now = new Date();
                
                // تجاهل المهام المنتهية
                if (scheduleTime < now) {
                    // تحديث الحالة إلى منتهية
                    const updateStmt = db.prepare(`
                        UPDATE scheduled_messages 
                        SET status = 'expired' 
                        WHERE job_id = ?
                    `);
                    updateStmt.run(msg.job_id);
                    continue;
                }
                
                // إعادة جدولة المهمة
                const result = scheduleMessage({
                    phone: msg.phone,
                    to: msg.to_number,
                    message: msg.message,
                    mediaPath: msg.media_path,
                    scheduleTime: scheduleTime,
                    repeat: msg.repeat_type,
                    repeatInterval: msg.repeat_interval
                });
                
                if (result.success) {
                    restoredCount++;
                }
                
            } catch (error) {
                console.error(`❌ فشل استعادة المهمة ${msg.job_id}:`, error.message);
            }
        }
        
        console.log(`🔄 تم استعادة ${restoredCount} مهمة مجدولة`);
        return restoredCount;
        
    } catch (error) {
        console.error("❌ فشل استعادة المهام المجدولة:", error);
        return 0;
    }
}

// ====== جدولة حالة (Status) ======
export function scheduleStatus({
    phone,
    message,
    mediaPath = null,
    scheduleTime,
    repeat = null
}) {
    try {
        const jobId = `status_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // التحقق من صحة الوقت
        if (!(scheduleTime instanceof Date) || isNaN(scheduleTime.getTime())) {
            throw new Error("الوقت غير صحيح");
        }
        
        if (scheduleTime <= new Date()) {
            throw new Error("لا يمكن جدولة حالة في الماضي");
        }
        
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
                
                console.log(`✅ تم تنفيذ الحالة المجدولة: ${jobId}`);
                
                // إرسال إشعار للمشرف
                const bot = getBot();
                if (bot && config.ADMIN_ID) {
                    await bot.telegram.sendMessage(
                        config.ADMIN_ID,
                        `✅ تم نشر الحالة المجدولة\n📋 المعرف: ${jobId}\n📱 من: ${phone}\n💬 ${message.substring(0, 100)}${message.length > 100 ? '...' : ''}`
                    );
                }
                
            } catch (error) {
                console.error(`❌ فشل تنفيذ الحالة المجدولة ${jobId}:`, error);
            }
        });
        
        if (!job) {
            throw new Error("فشل إنشاء الجدولة");
        }
        
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
        
        console.log(`✅ تم جدولة حالة: ${jobId} في ${scheduleTime.toLocaleString()}`);
        
        return {
            success: true,
            jobId,
            scheduledTime: scheduleTime,
            message: "تم جدولة الحالة بنجاح"
        };
        
    } catch (error) {
        console.error("❌ فشل جدولة الحالة:", error);
        throw new Error(`فشل جدولة الحالة: ${error.message}`);
    }
}

// ====== تنظيف المهام المنتهية ======
export function cleanupExpiredJobs() {
    try {
        const stmt = db.prepare(`
            UPDATE scheduled_messages 
            SET status = 'expired' 
            WHERE status = 'scheduled' 
            AND schedule_time < datetime('now')
        `);
        const result = stmt.run();
        
        if (result.changes > 0) {
            console.log(`🧹 تم تنظيف ${result.changes} مهمة منتهية`);
        }
        
        return result.changes;
    } catch (error) {
        console.error("❌ فشل تنظيف المهام:", error);
        return 0;
    }
}

// ====== تشغيل التنظيف التلقائي كل ساعة ======
export function startCleanupScheduler() {
    schedule.scheduleJob('0 * * * *', () => {
        cleanupExpiredJobs();
    });
    console.log("🧹 تم تشغيل جدولة التنظيف التلقائي (كل ساعة)");
}

export default {
    scheduleMessage,
    cancelScheduledMessage,
    getScheduledMessages,
    restoreScheduledMessages,
    scheduleStatus,
    cleanupExpiredJobs,
    startCleanupScheduler
}; 
