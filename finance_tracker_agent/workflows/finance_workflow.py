from typing import Dict, Any, Optional, Callable
import asyncio
import logging
from datetime import datetime
from agno.workflow import Workflow
from telegram import Update
from ..config.settings import settings
from ..tools.excel_tools import ExcelFinanceManager
from ..tools.telegram_tools import TelegramMessageHandler, TelegramBotTool
from ..agents.expense_agent import ExpenseTrackingAgent
from ..agents.budget_agent import BudgetMonitoringAgent
from ..agents.insights_agent import FinancialInsightsAgent

logger = logging.getLogger(__name__)


class FinanceTrackerWorkflow(Workflow):
    """Main workflow orchestrating all finance tracking agents."""
    
    def __init__(self):
        super().__init__(name="FinanceTracker")
        
        # Initialize tools
        self.excel_manager = ExcelFinanceManager(settings.excel_file_path)
        self.telegram_tool = TelegramBotTool(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id
        )
        
        # Initialize agents
        self.expense_agent = ExpenseTrackingAgent(self.excel_manager)
        self.budget_agent = BudgetMonitoringAgent(self.excel_manager)
        self.insights_agent = FinancialInsightsAgent(self.excel_manager, self.telegram_tool)
        
        # Initialize Telegram message handler
        self.message_handler = TelegramMessageHandler(
            token=settings.telegram_bot_token,
            message_callback=self.handle_telegram_message
        )
        
        logger.info("FinanceTrackerWorkflow initialized successfully")
    
    async def handle_telegram_message(self, message_type: str, update: Update) -> str:
        """Handle incoming Telegram messages and route to appropriate agents."""
        try:
            user_message = update.message.text
            user_id = update.effective_user.id
            chat_id = str(update.effective_chat.id)
            
            logger.info(f"Processing {message_type} message from user {user_id}: {user_message}")
            
            if message_type == "expense":
                # Handle expense logging
                response = await self.expense_agent.process_expense_message(user_message)
                
                # Check for budget alerts after logging expense
                if "✅" in response:  # Expense was logged successfully
                    # Extract expense data if needed for alerts
                    # This is simplified - in production would extract from agent response
                    pass
                
                return response
            
            elif message_type == "budget":
                # Handle budget-related commands
                return await self.budget_agent.process_budget_command(user_message)
            
            elif message_type == "balance":
                # Get current month spending summary
                return await self.get_balance_summary()
            
            elif message_type == "report":
                # Generate and send monthly report
                return await self.generate_monthly_report(chat_id)
            
            else:
                return """
🤖 I'm here to help with your finances!

Try these commands:
• Type expenses naturally: "Spent $25 on lunch"
• /budget - Manage your budgets
• /balance - Check current spending
• /report - Generate monthly report
• /help - Show all commands
"""
        
        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")
            return f"❌ Sorry, I encountered an error processing your message. Please try again."
    
    async def get_balance_summary(self) -> str:
        """Get current month spending balance summary."""
        try:
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            summary = self.excel_manager.get_spending_summary(current_month, current_year)
            
            if not summary["success"]:
                return "❌ Unable to retrieve balance information at this time."
            
            month_name = datetime.now().strftime("%B %Y")
            
            response = f"""
💰 <b>Balance Summary - {month_name}</b>

📊 <b>Overview</b>
• Total Spent: ${summary['total_spent']:.2f}
• Transactions: {summary['transaction_count']}
• Average per Transaction: ${summary['average_transaction']:.2f}

🏆 <b>Top Categories</b>
"""
            
            # Add top 5 categories
            if summary['category_breakdown']:
                sorted_categories = sorted(
                    summary['category_breakdown'].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                
                for i, (category, amount) in enumerate(sorted_categories[:5], 1):
                    percentage = (amount / summary['total_spent']) * 100 if summary['total_spent'] > 0 else 0
                    response += f"{i}. {category}: ${amount:.2f} ({percentage:.1f}%)\n"
            else:
                response += "No expenses recorded this month.\n"
            
            # Add budget status
            budget_data = self.excel_manager.get_budget_status()
            if budget_data["success"] and budget_data["budget_status"]:
                over_budget_categories = []
                warning_categories = []
                
                for budget in budget_data["budget_status"]:
                    if budget["status"] == "OVER BUDGET":
                        over_budget_categories.append(budget["category"])
                    elif budget["status"] == "WARNING":
                        warning_categories.append(budget["category"])
                
                if over_budget_categories:
                    response += f"\n⚠️ <b>Over Budget:</b> {', '.join(over_budget_categories)}"
                
                if warning_categories:
                    response += f"\n🟡 <b>Approaching Limit:</b> {', '.join(warning_categories)}"
                
                if not over_budget_categories and not warning_categories:
                    response += "\n✅ <b>All categories within budget!</b>"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting balance summary: {e}")
            return f"❌ Error retrieving balance: {str(e)}"
    
    async def generate_monthly_report(self, chat_id: str) -> str:
        """Generate and send monthly financial report."""
        try:
            # Send "generating report" message
            await self.telegram_tool.send_message(
                message="📊 Generating your monthly financial report...",
                chat_id=chat_id
            )
            
            # Generate the report
            return await self.insights_agent.send_monthly_report(chat_id)
            
        except Exception as e:
            logger.error(f"Error generating monthly report: {e}")
            return f"❌ Error generating report: {str(e)}"
    
    async def set_budget(self, category: str, amount: float) -> str:
        """Set budget for a category."""
        return await self.budget_agent.set_category_budget(category, amount)
    
    async def log_expense(
        self,
        amount: float,
        description: str,
        category: str,
        payment_method: str = "Unknown"
    ) -> str:
        """Log an expense through the expense agent."""
        return await self.expense_agent.log_expense(amount, description, category, payment_method)
    
    async def start_telegram_bot(self):
        """Start the Telegram bot polling."""
        try:
            logger.info("Starting Telegram bot...")
            await self.message_handler.start_polling()
            
            # Send startup notification if chat_id is configured
            if settings.telegram_chat_id:
                await self.telegram_tool.send_message(
                    message="""
🤖 <b>Finance Tracker Agent Started!</b>

I'm ready to help you manage your finances. 
Try sending me your first expense: "Spent $10 on coffee"

Type /help for all available commands.
""",
                    chat_id=settings.telegram_chat_id
                )
            
            # Keep the bot running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            await self.stop_telegram_bot()
        except Exception as e:
            logger.error(f"Error running Telegram bot: {e}")
            raise
    
    async def stop_telegram_bot(self):
        """Stop the Telegram bot polling."""
        try:
            logger.info("Stopping Telegram bot...")
            await self.message_handler.stop_polling()
            
            if settings.telegram_chat_id:
                await self.telegram_tool.send_message(
                    message="🤖 Finance Tracker Agent stopped. See you next time!",
                    chat_id=settings.telegram_chat_id
                )
                
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
    
    async def run_monthly_report_scheduler(self):
        """Schedule and send monthly reports automatically."""
        # This would implement scheduled monthly reports
        # For now, it's a placeholder for future functionality
        logger.info("Monthly report scheduler started (placeholder)")
        pass
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and health check."""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "excel_file_exists": settings.excel_file_path.exists(),
                "telegram_configured": bool(settings.telegram_bot_token),
                "ai_model_configured": bool(settings.anthropic_api_key or settings.openai_api_key),
                "agents_loaded": {
                    "expense_agent": self.expense_agent is not None,
                    "budget_agent": self.budget_agent is not None,
                    "insights_agent": self.insights_agent is not None
                }
            }
            
            # Check Excel file health
            if status["excel_file_exists"]:
                try:
                    summary = self.excel_manager.get_spending_summary()
                    status["excel_accessible"] = summary["success"]
                    status["total_expenses"] = summary.get("transaction_count", 0)
                except:
                    status["excel_accessible"] = False
                    status["total_expenses"] = 0
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}