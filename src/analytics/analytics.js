import db from "../database/db.js";

// ====== إحصائيات الحساب ======
export function getAccountStats(phone, days = 7) {
    const stmt = db.prepare(`
        SELECT 
            COUNT(*) as total_messages,
            SUM(CASE WHEN direction = 'incoming' THEN 1 ELSE 0 END) as received,
            SUM(CASE WHEN direction = 'outgoing' THEN 1 ELSE 0 END) as sent,
            COUNT(DISTINCT sender) as unique_contacts,
            DATE(created_at) as date
        FROM messages 
        WHERE phone = ? 
        AND created_at > datetime('now', ?)
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    `);
    
    const results = stmt.all(phone, `-${days} days`);
    
    // إحصائيات إجمالية
    const totalStmt = db.prepare(`
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN direction = 'incoming' THEN 1 ELSE 0 END) as received,
            SUM(CASE WHEN direction = 'outgoing' THEN 1 ELSE 0 END) as sent
        FROM messages 
        WHERE phone = ?
    `);
    const totals = totalStmt.get(phone);
    
    return {
        daily: results,
        totals: totals || { total: 0, received: 0, sent: 0 },
        days: days
    };
}

// ====== إحصائيات الحالات ======
export function getStatusStats(phone, days = 7) {
    const stmt = db.prepare(`
        SELECT 
            COUNT(*) as total_statuses,
            COUNT(DISTINCT status_id) as unique_statuses,
            SUM(views_count) as total_views,
            DATE(created_at) as date
        FROM statuses 
        WHERE phone = ? 
        AND created_at > datetime('now', ?)
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    `);
    
    return stmt.all(phone, `-${days} days`);
}

// ====== تقرير شامل ======
export function getFullReport(phone) {
    const accountStmt = db.prepare(`
        SELECT * FROM accounts WHERE phone = ?
    `);
    const account = accountStmt.get(phone);
    
    const messages = getAccountStats(phone);
    const statuses = getStatusStats(phone);
    
    // أكثر المراسلين نشاطاً
    const topContacts = db.prepare(`
        SELECT 
            sender,
            COUNT(*) as count
        FROM messages 
        WHERE phone = ? AND direction = 'incoming'
        GROUP BY sender 
        ORDER BY count DESC 
        LIMIT 10
    `).all(phone);
    
    return {
        account,
        messages,
        statuses,
        topContacts,
        generated_at: new Date().toISOString()
    };
}

// ====== تصدير التقرير كـ CSV ======
export function exportReportToCSV(phone) {
    const data = getFullReport(phone);
    
    let csv = 'التاريخ,الرسائل المستلمة,الرسائل المرسلة,المجموع\n';
    
    if (data.messages.daily) {
        for (const day of data.messages.daily) {
            csv += `${day.date},${day.received || 0},${day.sent || 0},${day.total_messages || 0}\n`;
        }
    }
    
    csv += `\nالإجمالي,${data.messages.totals.received},${data.messages.totals.sent},${data.messages.totals.total}\n`;
    
    return csv;
}

export default {
    getAccountStats,
    getStatusStats,
    getFullReport,
    exportReportToCSV
};
