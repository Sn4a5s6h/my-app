import db from '../database/db.js';
import { getAccount } from '../whatsapp/manager.js';

// ====== إنشاء مجموعة ======
export async function createGroup(phone, groupName, participants) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود أو غير متصل');
    }
    
    try {
        // تحويل الأرقام إلى JID
        const participantJids = participants.map(p => 
            p.includes('@') ? p : `${p}@s.whatsapp.net`
        );
        
        // إنشاء المجموعة
        const group = await sock.groupCreate(groupName, participantJids);
        
        // حفظ في قاعدة البيانات
        const stmt = db.prepare(`
            INSERT INTO groups (phone, group_id, group_name, participants, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        `);
        stmt.run(phone, group.id, groupName, JSON.stringify(participants));
        
        return {
            success: true,
            groupId: group.id,
            groupName: groupName,
            participants: participants
        };
    } catch (error) {
        throw new Error(`فشل إنشاء المجموعة: ${error.message}`);
    }
}

// ====== إضافة أعضاء للمجموعة ======
export async function addParticipants(phone, groupId, participants) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود');
    }
    
    try {
        const participantJids = participants.map(p => 
            p.includes('@') ? p : `${p}@s.whatsapp.net`
        );
        
        const result = await sock.groupParticipantsUpdate(
            groupId,
            participantJids,
            'add'
        );
        
        // تحديث قاعدة البيانات
        const group = db.prepare(`
            SELECT participants FROM groups WHERE group_id = ?
        `).get(groupId);
        
        if (group) {
            const currentParticipants = JSON.parse(group.participants);
            const newParticipants = [...new Set([...currentParticipants, ...participants])];
            
            const stmt = db.prepare(`
                UPDATE groups SET participants = ? WHERE group_id = ?
            `);
            stmt.run(JSON.stringify(newParticipants), groupId);
        }
        
        return {
            success: true,
            added: participants.length,
            result
        };
    } catch (error) {
        throw new Error(`فشل إضافة الأعضاء: ${error.message}`);
    }
}

// ====== إزالة أعضاء من المجموعة ======
export async function removeParticipants(phone, groupId, participants) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود');
    }
    
    try {
        const participantJids = participants.map(p => 
            p.includes('@') ? p : `${p}@s.whatsapp.net`
        );
        
        const result = await sock.groupParticipantsUpdate(
            groupId,
            participantJids,
            'remove'
        );
        
        // تحديث قاعدة البيانات
        const group = db.prepare(`
            SELECT participants FROM groups WHERE group_id = ?
        `).get(groupId);
        
        if (group) {
            const currentParticipants = JSON.parse(group.participants);
            const newParticipants = currentParticipants.filter(
                p => !participants.includes(p)
            );
            
            const stmt = db.prepare(`
                UPDATE groups SET participants = ? WHERE group_id = ?
            `);
            stmt.run(JSON.stringify(newParticipants), groupId);
        }
        
        return {
            success: true,
            removed: participants.length,
            result
        };
    } catch (error) {
        throw new Error(`فشل إزالة الأعضاء: ${error.message}`);
    }
}

// ====== تغيير اسم المجموعة ======
export async function updateGroupName(phone, groupId, newName) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود');
    }
    
    try {
        await sock.groupUpdateSubject(groupId, newName);
        
        const stmt = db.prepare(`
            UPDATE groups SET group_name = ? WHERE group_id = ?
        `);
        stmt.run(newName, groupId);
        
        return {
            success: true,
            groupId,
            newName
        };
    } catch (error) {
        throw new Error(`فشل تغيير الاسم: ${error.message}`);
    }
}

// ====== الحصول على معلومات المجموعة ======
export function getGroupInfo(groupId) {
    const stmt = db.prepare(`
        SELECT * FROM groups WHERE group_id = ?
    `);
    return stmt.get(groupId);
}

// ====== الحصول على جميع المجموعات ======
export function getAllGroups(phone = null) {
    let query = `SELECT * FROM groups`;
    const params = [];
    
    if (phone) {
        query += ` WHERE phone = ?`;
        params.push(phone);
    }
    
    query += ` ORDER BY created_at DESC`;
    
    const stmt = db.prepare(query);
    return stmt.all(...params);
}

// ====== إرسال رسالة للمجموعة ======
export async function sendGroupMessage(phone, groupId, message, mediaPath = null) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود');
    }
    
    try {
        let result;
        
        if (mediaPath) {
            // إرسال مع ميديا
            const mediaBuffer = require('fs').readFileSync(mediaPath);
            result = await sock.sendMessage(groupId, {
                image: mediaBuffer,
                caption: message
            });
        } else {
            // إرسال نص
            result = await sock.sendMessage(groupId, { text: message });
        }
        
        // حفظ في قاعدة البيانات
        const stmt = db.prepare(`
            INSERT INTO messages (phone, direction, sender, receiver, message, status)
            VALUES (?, ?, ?, ?, ?, ?)
        `);
        stmt.run(phone, 'outgoing', phone + '@s.whatsapp.net', groupId, message, 'sent');
        
        return {
            success: true,
            groupId,
            messageId: result.key.id
        };
    } catch (error) {
        throw new Error(`فشل إرسال رسالة للمجموعة: ${error.message}`);
    }
}

// ====== مغادرة المجموعة ======
export async function leaveGroup(phone, groupId) {
    const sock = getAccount(phone);
    if (!sock) {
        throw new Error('الحساب غير موجود');
    }
    
    try {
        await sock.groupLeave(groupId);
        
        // حذف من قاعدة البيانات
        const stmt = db.prepare(`
            DELETE FROM groups WHERE group_id = ?
        `);
        stmt.run(groupId);
        
        return {
            success: true,
            groupId
        };
    } catch (error) {
        throw new Error(`فشل مغادرة المجموعة: ${error.message}`);
    }
}

export default {
    createGroup,
    addParticipants,
    removeParticipants,
    updateGroupName,
    getGroupInfo,
    getAllGroups,
    sendGroupMessage,
    leaveGroup
};
