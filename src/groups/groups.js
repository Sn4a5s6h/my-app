import db from "../database/db.js";

// ====== الحصول على قائمة المجموعات ======
export async function getGroups(phone, sock) {
    try {
        const groups = await sock.groupFetchAllParticipating();
        const groupList = Object.values(groups);
        
        // حفظ في قاعدة البيانات
        const stmt = db.prepare(`
            INSERT OR REPLACE INTO groups (
                phone, group_id, group_name, participants, updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        `);
        
        for (const group of groupList) {
            stmt.run(
                phone,
                group.id,
                group.subject,
                JSON.stringify(group.participants || [])
            );
        }
        
        return groupList;
        
    } catch (error) {
        console.error(`❌ Failed to get groups:`, error);
        return [];
    }
}

// ====== إرسال رسالة للمجموعة ======
export async function sendToGroup(phone, groupId, message, sock) {
    try {
        const result = await sock.sendMessage(groupId, { text: message });
        
        // تسجيل في قاعدة البيانات
        const stmt = db.prepare(`
            INSERT INTO messages (phone, direction, sender, receiver, message, status)
            VALUES (?, ?, ?, ?, ?, ?)
        `);
        stmt.run(phone, 'outgoing', phone + '@s.whatsapp.net', groupId, message, 'sent');
        
        return result;
        
    } catch (error) {
        throw new Error(`فشل إرسال للمجموعة: ${error.message}`);
    }
}

// ====== الحصول على معلومات المجموعة ======
export function getGroupInfo(phone, groupId) {
    const stmt = db.prepare(`
        SELECT * FROM groups 
        WHERE phone = ? AND group_id = ?
    `);
    return stmt.get(phone, groupId);
}

// ====== الحصول على جميع المجموعات لحساب معين ======
export function getGroupsForAccount(phone) {
    const stmt = db.prepare(`
        SELECT * FROM groups 
        WHERE phone = ? 
        ORDER BY group_name ASC
    `);
    return stmt.all(phone);
}

export default {
    getGroups,
    sendToGroup,
    getGroupInfo,
    getGroupsForAccount
};
