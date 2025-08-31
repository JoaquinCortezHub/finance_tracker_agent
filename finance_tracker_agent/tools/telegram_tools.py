from typing import Optional, Dict, Any, List
from agno.tools import Toolkit
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TelegramBotTool(Toolkit):
    """Tool for interacting with Telegram Bot API."""
    
    def __init__(self, token: str, chat_id: Optional[str] = None):
        super().__init__()
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.app = Application.builder().token(token).build()
        
    async def send_message(
        self, 
        message: str, 
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = "HTML"
    ) -> Dict[str, Any]:
        """Send a message to the specified chat."""
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("No chat_id provided and no default chat_id set")
            
        try:
            sent_message = await self.bot.send_message(
                chat_id=target_chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return {
                "success": True,
                "message_id": sent_message.message_id,
                "text": sent_message.text
            }
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_photo(
        self,
        photo_path: Path,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a photo to the specified chat."""
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("No chat_id provided and no default chat_id set")
            
        try:
            with open(photo_path, 'rb') as photo:
                sent_message = await self.bot.send_photo(
                    chat_id=target_chat_id,
                    photo=photo,
                    caption=caption
                )
            return {
                "success": True,
                "message_id": sent_message.message_id,
                "caption": sent_message.caption
            }
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_chat_info(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Get information about the chat."""
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("No chat_id provided and no default chat_id set")
            
        try:
            chat = await self.bot.get_chat(chat_id=target_chat_id)
            return {
                "success": True,
                "chat_id": chat.id,
                "type": chat.type,
                "title": getattr(chat, 'title', None),
                "username": getattr(chat, 'username', None)
            }
        except Exception as e:
            logger.error(f"Failed to get chat info: {e}")
            return {"success": False, "error": str(e)}


class TelegramMessageHandler:
    """Handles incoming Telegram messages and routes them to appropriate agents."""
    
    def __init__(self, token: str, message_callback=None):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.message_callback = message_callback
        self.setup_handlers()
    
    def setup_handlers(self):
        """Set up message handlers."""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("budget", self.budget_command))
        self.app.add_handler(CommandHandler("report", self.report_command))
        
        # Message handler for expenses and general messages
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handle_message
        ))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = """
🤖 Welcome to your Finance Tracker Agent!

I'm here to help you manage your personal finances. Here's what I can do:

💰 <b>Expense Tracking</b>
- Log expenses by simply typing: "Spent $25 on lunch"
- I'll automatically categorize and add them to your spreadsheet

📊 <b>Budget Management</b>
- Set budget goals with /budget command
- Get alerts when you're approaching limits

📈 <b>Financial Insights</b>
- Monthly reports with /report command
- Visual charts and spending analysis

Commands:
/help - Show this help message
/balance - Check current month's spending
/budget - Set or view budget goals
/report - Generate monthly financial report

Just start typing your expenses naturally, and I'll take care of the rest!
        """
        await update.message.reply_text(welcome_message, parse_mode="HTML")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = """
<b>Finance Tracker Commands:</b>

/start - Welcome message and introduction
/help - This help message
/balance - Check current spending balance
/budget - Set or view budget goals
/report - Generate monthly financial report

<b>Expense Logging Examples:</b>
• "Spent $25 on lunch at McDonald's"
• "Paid $150 for groceries"
• "Gas $45"
• "Movie tickets $28"

I'll automatically:
✅ Extract the amount and description
✅ Categorize the expense
✅ Add it to your Excel spreadsheet
✅ Check against your budget goals
        """
        await update.message.reply_text(help_message, parse_mode="HTML")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command."""
        if self.message_callback:
            response = await self.message_callback("balance", update)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("Balance checking not configured yet.")
    
    async def budget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /budget command."""
        if self.message_callback:
            response = await self.message_callback("budget", update)
            await update.message.reply_text(response, parse_mode="HTML")
        else:
            await update.message.reply_text("Budget management not configured yet.")
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command."""
        if self.message_callback:
            response = await self.message_callback("report", update)
            await update.message.reply_text(response, parse_mode="HTML")
        else:
            await update.message.reply_text("Report generation not configured yet.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text messages (expense logging)."""
        if self.message_callback:
            response = await self.message_callback("expense", update)
            await update.message.reply_text(response, parse_mode="HTML")
        else:
            await update.message.reply_text("Message processing not configured yet.")
    
    async def start_polling(self):
        """Start the bot polling."""
        logger.info("Starting Telegram bot polling...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
    
    async def stop_polling(self):
        """Stop the bot polling."""
        logger.info("Stopping Telegram bot polling...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()