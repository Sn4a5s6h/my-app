import db from '../database/db.js';
import { accounts } from '../whatsapp/manager.js';

// ====== الحصول على إحصائيات عامة ======
export function getGeneralStats() {
    const stats = {};
    
    // عدد الحسابات
    const accountsCount = db.prepare(`
        SELECT COUNT(*) as count FROM accounts
    `).get();
    stats.totalAccounts = accountsCount.count;
    
    // عدد الحسابات المتصلة
    const connectedCount = db.prepare(`
        SELECT COUNT(*) as count FROM accounts WHERE status = 'connected'
    `).get();
    stats.connectedAccounts = connectedCount.count;
    
    // عدد الرسائل اليوم
    const today = new Date().toISOString().split('T')[0];
    const messagesToday = db.prepare(`
        SELECT COUNT(*) as count FROM messages 
        WHERE date(created_at) = ?
    `).get(today);
    stats.messagesToday = messagesToday.count;
    
    // عدد الرسائل الكلي
    const totalMessages = db.prepare(`
        SELECT COUNT(*) as count FROM messages
    `).get();
    stats.totalMessages = totalMessages.count;
    
    // عدد الحالات
    const totalStatuses = db.prepare(`
        SELECT COUNT(*) as count FROM statuses
    `).get();
    stats.totalStatuses = totalStatuses.count;
    
    // عدد المجموعات
    const totalGroups = db.prepare(`
        SELECT COUNT(*) as count FROM groups
    `).get();
    stats.totalGroups = totalGroups.count;
    
    // عدد المهام المجدولة
    const scheduledPending = db.prepare(`
        SELECT COUNT(*) as count FROM scheduled_messages 
        WHERE status = 'pending'
    `).get();
    stats.scheduledPending = scheduledPending.count;
    
    // عدد الردود التلقائية
    const totalAutoReplies = db.prepare(`
        SELECT COUNT(*) as count FROM auto_reply_rules 
        WHERE enabled = 1
    `).get();
    stats.totalAutoReplies = totalAutoReplies.count;
    
    return stats;
}

// ====== إحصائيات كل حساب ======
export function getAccountStats(phone) {
    const stats = {};
    
    // عدد الرسائل المرسلة
    const sent = db.prepare(`
        SELECT COUNT(*) as count FROM messages 
        WHERE phone = ? AND direction = 'outgoing'
    `).get(phone);
    stats.sent = sent.count;
    
    // عدد الرسائل المستلمة
    const received = db.prepare(`
        SELECT COUNT(*) as count FROM messages 
        WHERE phone = ? AND direction = 'incoming'
    `).get(phone);
    stats.received = received.count;
    
    // عدد الحالات المنشورة
    const statuses = db.prepare(`
        SELECT COUNT(*) as count FROM statuses 
        WHERE phone = ?
    `).get(phone);
    stats.statuses = statuses.count;
    
    // عدد المجموعات
    const groups = db.prepare(`
        SELECT COUNT(*) as count FROM groups 
        WHERE phone = ?
    `).get(phone);
    stats.groups = groups.count;
    
    // عدد المهام المجدولة
    const scheduled = db.prepare(`
        SELECT COUNT(*) as count FROM scheduled_messages 
        WHERE phone = ? AND status = 'pending'
    `).get(phone);
    stats.scheduled = scheduled.count;
    
    // عدد الردود التلقائية
    const autoReplies = db.prepare(`
        SELECT COUNT(*) as count FROM auto_reply_rules 
        WHERE phone = ? AND enabled = 1
    `).get(phone);
    stats.autoReplies = autoReplies.count;
    
    return stats;
}

// ====== إحصائيات الرسائل الشهرية ======
export function getMonthlyStats(phone = null) {
    let query = `
        SELECT 
            strftime('%Y-%m', created_at) as month,
            direction,
            COUNT(*) as count
        FROM messages 
    `;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` GROUP BY month, direction ORDER BY month DESC LIMIT 12`;
    
    const stmt = db.prepare(query);
    const results = stmt.all(...params);
    
    // تحويل البيانات
    const monthlyData = {};
    for (const row of results) {
        if (!monthlyData[row.month]) {
            monthlyData[row.month] = { sent: 0, received: 0 };
        }
        monthlyData[row.month][row.direction] = row.count;
    }
    
    return monthlyData;
}

// ====== إحصائيات الرسائل اليومية ======
export function getDailyStats(phone = null, days = 7) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().split('T')[0];
    
    let query = `
        SELECT 
            date(created_at) as day,
            direction,
            COUNT(*) as count
        FROM messages 
        WHERE date(created_at) >= ?
    `;
    const params = [cutoffStr];
    
    if (phone) {
        query += ` AND phone = ?`;
        params.push(phone);
    }
    
    query += ` GROUP BY day, direction ORDER BY day ASC`;
    
    const stmt = db.prepare(query);
    const results = stmt.all(...params);
    
    // تحويل البيانات
    const dailyData = {};
    for (const row of results) {
        if (!dailyData[row.day]) {
            dailyData[row.day] = { sent: 0, received: 0 };
        }
        dailyData[row.day][row.direction] = row.count;
    }
    
    return dailyData;
}

// ====== إحصائيات مشاهدات الحالات ======
export function getStatusStats(phone = null) {
    let query = `
        SELECT 
            phone,
            COUNT(*) as total,
            SUM(CASE WHEN is_viewed = 1 THEN 1 ELSE 0 END) as viewed
        FROM statuses 
    `;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` GROUP BY phone`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== أكثر الأرقام نشاطاً ======
export function getTopActiveNumbers(limit = 10) {
    const stmt = db.prepare(`
        SELECT 
            sender,
            COUNT(*) as message_count,
            MAX(created_at) as last_active
        FROM messages 
        WHERE direction = 'incoming'
        GROUP BY sender 
        ORDER BY message_count DESC 
        LIMIT ?
    `);
    return stmt.all(limit);
}

// ====== رسائل اليوم بالوقت ======
export function getHourlyDistribution(phone = null) {
    let query = `
        SELECT 
            strftime('%H', created_at) as hour,
            direction,
            COUNT(*) as count
        FROM messages 
        WHERE date(created_at) = date('now')
    `;
    const params = [];
    
    if (phone) {
        query += ` AND phone = ?`;
        params.push(phone);
    }
    
    query += ` GROUP BY hour, direction ORDER BY hour`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== أداء الحسابات ======
export function getAccountPerformance(phone) {
    const stats = getAccountStats(phone);
    const daily = getDailyStats(phone, 30);
    
    // حساب متوسط الرسائل اليومية
    const days = Object.keys(daily).length || 1;
    const avgDaily = {
        sent: Math.round(stats.sent / days),
        received: Math.round(stats.received / days)
    };
    
    // نسبة الاستجابة
    const responseRate = stats.received > 0 
        ? Math.round((stats.sent / stats.received) * 100) 
        : 0;
    
    return {
        total: stats,
        averageDaily: avgDaily,
        responseRate: responseRate,
        daysActive: days
    };
}

// ====== تقرير كامل ======
export function getFullReport() {
    return {
        general: getGeneralStats(),
        topActive: getTopActiveNumbers(10),
        monthly: getMonthlyStats(),
        daily: getDailyStats(null, 7),
        statuses: getStatusStats(),
        timestamp: new Date().toISOString()
    };
}

export default {
    getGeneralStats,
    getAccountStats,
    getMonthlyStats,
    getDailyStats,
    getStatusStats,
    getTopActiveNumbers,
    getHourlyDistribution,
    getAccountPerformance,
    getFullReport
};
