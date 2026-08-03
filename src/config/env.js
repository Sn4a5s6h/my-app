import dotenv from "dotenv";

dotenv.config();

export default {
    PORT: process.env.PORT || 3000,
    TELEGRAM_TOKEN: process.env.TELEGRAM_TOKEN,
    ADMIN_ID: process.env.ADMIN_TELEGRAM_ID
};
