import {
makeWASocket,
useMultiFileAuthState,
fetchLatestBaileysVersion
} from "@whiskeysockets/baileys";

import fs from "fs";


const sessions = new Map();


export async function addAccount(phone){

const folder=`sessions/${phone}`;

if(!fs.existsSync(folder))
fs.mkdirSync(folder,{recursive:true});


const {state,saveCreds}=await useMultiFileAuthState(folder);

const {version}=await fetchLatestBaileysVersion();


const sock=makeWASocket({

version,
auth:state,
printQRInTerminal:true

});


sock.ev.on(
"creds.update",
saveCreds
);


sock.ev.on(
"connection.update",
(update)=>{

console.log(
phone,
update.connection
);

});


sock.ev.on(
"messages.upsert",
(data)=>{

console.log(
"NEW MESSAGE",
data.messages[0]
);

});


sessions.set(phone,sock);


return sock;

}



export function getAccount(phone){

return sessions.get(phone);

}


export function accounts(){

return [...sessions.keys()];

  }
