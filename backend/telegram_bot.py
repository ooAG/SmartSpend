import os
import sys
import httpx
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# 1. Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 2. Configuration
BOT_TOKEN = "8597106839:AAGxovBVMyjchALHqZellQBln6ijXxw0-gg"
BASE_URL = "http://127.0.0.1:8000" 

# --- UI HELPERS ---

def get_confirm_keyboard(data):
    """Generates the primary transaction menu with dynamic data."""
    m_short = str(data.get('merchant', 'Unknown'))[:15].replace('|', '')
    c_short = str(data.get('category', 'Others'))[:10].replace('|', '')
    amt = data.get('amount', 0)
    t_type = data.get('type', 'debit')
    
    cb_save = f"save|{amt}|{t_type}|{m_short}|{c_short}"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Save", callback_data=cb_save)],
        [
            InlineKeyboardButton("✏️ Amt", callback_data="edit_amt"),
            InlineKeyboardButton("✏️ Name", callback_data="edit_name"),
            InlineKeyboardButton("✏️ Cat", callback_data="edit_cat")
        ],
        [InlineKeyboardButton("❌ Discard", callback_data="ask_discard")]
    ])

def get_discard_keyboard():
    """Safety menu for discarding a transaction."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Yes, Discard", callback_data="confirm_discard")],
        [InlineKeyboardButton("🔙 No, Go Back", callback_data="back_to_menu")]
    ])

# --- MESSAGE HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    temp_data = context.user_data.get("editing_txn")
    is_reply = update.message.reply_to_message is not None

    # 🟢 BLOCK 1: Processing Edits (Strict Logic)
    if is_reply and temp_data:
        reply_text = update.message.reply_to_message.text.lower()
        updated = False
        
        if "amount" in reply_text:
            try:
                # Clean numeric input
                clean_amt = text.replace('₹', '').strip()
                temp_data["amount"] = float(clean_amt)
                updated = True
            except ValueError:
                context.user_data.clear()
                await update.message.reply_text("task terminated due to wrong input")
                return 
        elif "name" in reply_text:
            temp_data["merchant"] = text
            updated = True
        elif "category" in reply_text:
            temp_data["category"] = text
            updated = True
        else:
            context.user_data.clear()
            await update.message.reply_text("task terminated due to wrong input")
            return

        if updated:
            context.user_data["editing_txn"] = temp_data
            await update.message.reply_text(
                f"✨ **Details Updated**\n\n"
                f"💰 **Amount:** ₹{temp_data['amount']}\n"
                f"🏢 **Merchant:** {temp_data['merchant']}\n"
                f"📂 **Category:** {temp_data['category']}",
                reply_markup=get_confirm_keyboard(temp_data),
                parse_mode="Markdown"
            )
            return 

    # 🔴 BLOCK 2: SMS Parsing (Async for Speed)
    async with httpx.AsyncClient() as client:
        try:
            parse_res = await client.post(f"{BASE_URL}/api/parse_sms", data={"text": text}, timeout=10.0)
            
            if parse_res.status_code == 200:
                data = parse_res.json()
                amt = float(data.get("amount", 0))
                merch = data.get("merchant", "Unknown")
                
                # Filter Garbage (8fffh, A, etc.)
                if amt == 0 or merch == "Unknown":
                    await update.message.reply_text("Invalid Input ❌")
                    return

                context.user_data["editing_txn"] = data
                await update.message.reply_text(
                    f"🔍 **Transaction Detected**\n\n"
                    f"💰 **Amount:** ₹{amt}\n"
                    f"🏢 **Merchant:** {merch}\n"
                    f"📂 **Category:** {data.get('category', 'Others')}",
                    reply_markup=get_confirm_keyboard(data),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("Invalid Input ❌")
                
        except Exception as e:
            logger.error(f"Parse Failure: {e}")
            await update.message.reply_text("Invalid Input ❌")

# --- CALLBACK HANDLERS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    temp_data = context.user_data.get("editing_txn")

    if query.data == "ask_discard":
        await query.edit_message_text(
            "⚠️ **Confirm Action**\nAre you sure you want to discard this entry?",
            reply_markup=get_discard_keyboard(),
            parse_mode="Markdown"
        )
        return

    if query.data == "confirm_discard":
        context.user_data.clear()
        await query.edit_message_text("❌ Transaction discarded.")
        return

    if query.data == "back_to_menu" and temp_data:
        await query.edit_message_text(
            f"🔍 **Transaction Detected**\n\n"
            f"💰 **Amount:** ₹{temp_data['amount']}\n"
            f"🏢 **Merchant:** {temp_data['merchant']}\n"
            f"📂 **Category:** {temp_data['category']}",
            reply_markup=get_confirm_keyboard(temp_data),
            parse_mode="Markdown"
        )
        return

    prompts = {
        "edit_amt": "📝 **Edit Amount**\nPlease reply with the new numeric value:",
        "edit_name": "📝 **Edit Name**\nPlease reply with the correct merchant name:",
        "edit_cat": "📝 **Edit Category**\nPlease reply with the new category:"
    }
    
    if query.data in prompts:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=prompts[query.data],
            reply_markup=ForceReply(selective=True),
            parse_mode="Markdown"
        )
        return

    if query.data.startswith("save"):
        parts = query.data.split('|')
        tel_id = str(query.from_user.id)
        
        async with httpx.AsyncClient() as client:
            try:
                save_res = await client.post(f"{BASE_URL}/api/save_transaction", data={
                    "amount": parts[1], 
                    "type": parts[2], 
                    "merchant": parts[3], 
                    "category": parts[4]
                }, params={"telegram_id": tel_id}, timeout=10.0)
                
                if save_res.status_code == 200:
                    context.user_data.clear()
                    await query.edit_message_text(f"✅ **Saved:** ₹{parts[1]} at {parts[3]}")
                else:
                    await query.edit_message_text("❌ **Save Failed:** Please check your link status.")
            except Exception as e:
                logger.error(f"Save Failure: {e}")
                await query.edit_message_text("❌ **Server Error:** Could not save transaction.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **SmartSpend Bot Active**\n\nSend me a bank SMS, and I will help you track it. "
        "Use `/start email@example.com` to link your account.",
        parse_mode="Markdown"
    )

# --- APP INITIALIZATION ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.add_handler(CallbackQueryHandler(handle_callback))

if __name__ == '__main__':
    print("🚀 SmartSpend Bot is now online...")
    app.run_polling(drop_pending_updates=True)