from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from enum import Enum
import re
import json
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.tools.reasoning import ReasoningTools
from ..tools.excel_tools import ExcelFinanceManager
from ..config.settings import settings
from .expense_agent import ExpenseTrackingAgent
from .budget_agent import BudgetMonitoringAgent
from .insights_agent import FinancialInsightsAgent
from .onboarding_agent import OnboardingAgent
import logging

logger = logging.getLogger(__name__)


class UserState(Enum):
    """User onboarding and interaction states."""
    NEW_USER = "new_user"
    AWAITING_BALANCE = "awaiting_balance"
    AWAITING_BUDGETS = "awaiting_budgets"
    ACTIVE = "active"


class FinanceManagerAgent(Agent):
    """
    Central manager agent that interprets user messages and delegates to specialized agents.
    Handles user onboarding, maintains conversation context, and orchestrates workflow.
    """
    
    def __init__(self, excel_manager: ExcelFinanceManager):
        # Choose model based on available API keys
        if settings.anthropic_api_key:
            model = Claude(
                id="claude-sonnet-4-20250514", 
                api_key=settings.anthropic_api_key,
                reasoning_effort="medium"
            )
        elif settings.openai_api_key:
            model = OpenAIChat(
                id="gpt-5", 
                api_key=settings.openai_api_key,
                reasoning_effort="medium"
            )
        else:
            raise ValueError("No API key provided for AI model")
        
        super().__init__(
            model=model,
            tools=[ReasoningTools(add_instructions=True)],
            instructions=self._get_instructions(),
            name="FinanceManager",
            role="Personal Finance Management Orchestrator",
            markdown=True,
            show_tool_calls=True
        )
        
        self.excel_manager = excel_manager
        self._initialize_specialized_agents()
        
        # User state tracking (in production, store in database)
        self.user_states: Dict[str, UserState] = {}
        self.conversation_context: Dict[str, List[Dict[str, Any]]] = {}
        
    def _initialize_specialized_agents(self) -> None:
        """Initialize all specialized agents."""
        try:
            self.expense_agent = ExpenseTrackingAgent(self.excel_manager)
            self.budget_agent = BudgetMonitoringAgent(self.excel_manager)
            self.insights_agent = FinancialInsightsAgent(self.excel_manager)
            self.onboarding_agent = OnboardingAgent(self.excel_manager)
            logger.info("All specialized agents initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize specialized agents: {e}")
            raise
    
    def _get_instructions(self) -> str:
        """Get manager agent instructions using GPT-5 best practices."""
        return f"""
<role>
You are a Personal Finance Management Orchestrator, responsible for intelligently interpreting user messages and delegating tasks to specialized financial agents.
</role>

<capabilities>
- **Intent Classification**: Determine user intent from natural language messages
- **User Onboarding**: Guide new users through balance and budget setup
- **Task Delegation**: Route requests to appropriate specialized agents
- **Context Management**: Maintain conversation flow and user state
- **Response Coordination**: Synthesize responses from multiple agents when needed
</capabilities>

<specialized_agents>
- **OnboardingAgent**: Handles new user setup (balance, budgets)
- **ExpenseAgent**: Processes expense logging and categorization  
- **BudgetAgent**: Manages budget creation, monitoring, and alerts
- **InsightsAgent**: Generates financial reports and analysis
</specialized_agents>

<user_states>
- **NEW_USER**: First-time user, needs complete onboarding
- **AWAITING_BALANCE**: User needs to set initial balance
- **AWAITING_BUDGETS**: User needs to create budgets
- **ACTIVE**: Fully onboarded, can use all features
</user_states>

<intent_categories>
1. **ONBOARDING**: Setting up balance, creating budgets, initial setup
2. **EXPENSE**: Logging expenses, recording transactions
3. **BUDGET**: Managing budgets, checking limits, modifying allocations
4. **INSIGHTS**: Reports, analysis, spending patterns, recommendations
5. **BALANCE**: Current balance, spending summaries, account status
6. **HELP**: Commands, guidance, feature explanations
7. **GENERAL**: Greetings, small talk, unclear requests
</intent_categories>

<decision_framework>
1. **Check User State**: Determine if user needs onboarding
2. **Classify Intent**: Analyze message for primary intent
3. **Context Analysis**: Consider conversation history and user state
4. **Agent Selection**: Choose appropriate specialized agent(s)
5. **Response Synthesis**: Coordinate multi-agent responses if needed
</decision_framework>

<response_guidelines>
- **Be Conversational**: Use natural, helpful tone with appropriate emojis
- **Provide Context**: Explain what you're doing when delegating
- **Track Progress**: Update user state as they complete onboarding steps
- **Handle Ambiguity**: Ask clarifying questions for unclear requests
- **Maintain Flow**: Keep conversations smooth and purposeful
</response_guidelines>

<formatting>
Use **Markdown formatting** for clear structure:
- **Bold** for emphasis and section headers
- Emojis for visual appeal and categorization
- Bullet points for lists and options
- Code blocks for structured data when appropriate
</formatting>

<error_handling>
- Gracefully handle agent failures with fallback responses
- Guide users to rephrase unclear requests
- Provide helpful alternatives when primary intent fails
- Never expose technical errors to users
</error_handling>

Current system configuration:
- Default currency: {settings.default_currency}
- Available categories: {', '.join(settings.expense_categories)}
- Excel file location: {settings.excel_file_path}
"""

    async def process_user_message(
        self,
        message: str,
        user_id: str,
        chat_id: str
    ) -> str:
        """
        Main entry point for processing user messages.
        Handles state management, intent classification, and agent delegation.
        """
        try:
            # Initialize user state if new
            if user_id not in self.user_states:
                await self._initialize_new_user(user_id)
            
            current_state = self.user_states[user_id]
            
            # Handle onboarding flow
            if current_state != UserState.ACTIVE:
                return await self._handle_onboarding_message(
                    message, user_id, chat_id, current_state
                )
            
            # For active users, classify intent and delegate
            intent = await self._classify_intent(message, user_id)
            return await self._delegate_to_agent(message, intent, user_id, chat_id)
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            return "❌ I encountered an error processing your request. Please try again in a moment."

    async def _initialize_new_user(self, user_id: str) -> None:
        """Initialize a new user and determine their onboarding needs."""
        try:
            # Check if user has existing data
            user_data = self.excel_manager.get_user_setup_status()
            
            if user_data.get("has_balance") and user_data.get("has_budgets"):
                self.user_states[user_id] = UserState.ACTIVE
                logger.info(f"User {user_id} recognized as returning user")
            else:
                self.user_states[user_id] = UserState.NEW_USER
                logger.info(f"New user {user_id} initialized for onboarding")
                
            # Initialize conversation context
            self.conversation_context[user_id] = []
            
        except Exception as e:
            logger.error(f"Failed to initialize user {user_id}: {e}")
            self.user_states[user_id] = UserState.NEW_USER

    async def _handle_onboarding_message(
        self,
        message: str,
        user_id: str,
        chat_id: str,
        current_state: UserState
    ) -> str:
        """Handle messages during user onboarding flow."""
        try:
            response = await self.onboarding_agent.process_onboarding_step(
                message=message,
                user_id=user_id,
                current_state=current_state.value
            )
            
            # Update user state based on onboarding progress
            if "onboarding_complete" in response.lower():
                self.user_states[user_id] = UserState.ACTIVE
                logger.info(f"User {user_id} completed onboarding")
            elif "balance_set" in response.lower():
                self.user_states[user_id] = UserState.AWAITING_BUDGETS
            elif "awaiting_balance" in response.lower():
                self.user_states[user_id] = UserState.AWAITING_BALANCE
                
            return response
            
        except Exception as e:
            logger.error(f"Error handling onboarding for user {user_id}: {e}")
            return "❌ There was an issue with your setup. Let me help you start over."

    async def _classify_intent(self, message: str, user_id: str) -> str:
        """Classify user message intent using GPT-5's reasoning capabilities."""
        try:
            classification_prompt = f"""
<task>
Classify the user's intent from their message for a personal finance management system.
</task>

<message>
"{message}"
</message>

<intent_options>
1. EXPENSE - Logging expenses, recording transactions
2. BUDGET - Managing budgets, checking limits, modifying allocations  
3. INSIGHTS - Reports, analysis, spending patterns, recommendations
4. BALANCE - Current balance, spending summaries, account status
5. HELP - Commands, guidance, feature explanations
6. GENERAL - Greetings, small talk, unclear requests
</intent_options>

<classification_rules>
- Look for expense indicators: amounts, "spent", "paid", "bought", merchant names
- Look for budget indicators: "budget", "limit", "allowance", category management
- Look for insight indicators: "report", "analysis", "trends", "recommendations"
- Look for balance indicators: "balance", "total", "summary", "how much"
- Default to GENERAL for ambiguous messages
</classification_rules>

<output_format>
Return only the intent category name (e.g., "EXPENSE", "BUDGET", etc.)
</output_format>
"""
            
            response = await self.arun(classification_prompt)
            intent = response.strip().upper()
            
            # Validate intent
            valid_intents = ["EXPENSE", "BUDGET", "INSIGHTS", "BALANCE", "HELP", "GENERAL"]
            if intent not in valid_intents:
                intent = "GENERAL"
            
            logger.info(f"Classified message intent as: {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"Failed to classify intent: {e}")
            return "GENERAL"

    async def _delegate_to_agent(
        self,
        message: str,
        intent: str,
        user_id: str,
        chat_id: str
    ) -> str:
        """Delegate message to appropriate specialized agent based on intent."""
        try:
            if intent == "EXPENSE":
                return await self.expense_agent.process_expense_message(message)
                
            elif intent == "BUDGET":
                return await self.budget_agent.process_budget_command(message)
                
            elif intent == "INSIGHTS":
                return await self.insights_agent.generate_monthly_report()
                
            elif intent == "BALANCE":
                return await self._get_balance_summary()
                
            elif intent == "HELP":
                return self._get_help_message()
                
            else:  # GENERAL
                return await self._handle_general_message(message, user_id)
                
        except Exception as e:
            logger.error(f"Error delegating to agent for intent {intent}: {e}")
            return f"❌ I had trouble processing your {intent.lower()} request. Please try rephrasing."

    async def _get_balance_summary(self) -> str:
        """Get comprehensive balance summary."""
        try:
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            summary = self.excel_manager.get_spending_summary(current_month, current_year)
            
            if not summary["success"]:
                return "❌ Unable to retrieve balance information at this time."
            
            month_name = datetime.now().strftime("%B %Y")
            
            response = f"""
💰 **Balance Summary - {month_name}**

📊 **Overview**
• Total Spent: ${summary['total_spent']:.2f}
• Transactions: {summary['transaction_count']}
• Average per Transaction: ${summary['average_transaction']:.2f}

🏆 **Top Categories**
"""
            
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
                over_budget = [b["category"] for b in budget_data["budget_status"] if b["status"] == "OVER BUDGET"]
                warning = [b["category"] for b in budget_data["budget_status"] if b["status"] == "WARNING"]
                
                if over_budget:
                    response += f"\n⚠️ **Over Budget:** {', '.join(over_budget)}"
                if warning:
                    response += f"\n🟡 **Approaching Limit:** {', '.join(warning)}"
                if not over_budget and not warning:
                    response += "\n✅ **All categories within budget!**"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting balance summary: {e}")
            return "❌ Error retrieving balance information."

    def _get_help_message(self) -> str:
        """Get comprehensive help message."""
        return """
🤖 **Personal Finance Assistant Help**

📝 **Logging Expenses**
Just type naturally:
• "Spent $25 on lunch at Joe's"
• "Gas $45"
• "Coffee $4.50"
• "$28 movie tickets"

💰 **Budget Management**
• `/budget set Food 500` - Set monthly budget
• `/budget check` - View all budgets
• `/budget Food` - Check specific category

📊 **Reports & Analysis**
• `/balance` - Current month summary
• `/report` - Detailed monthly report
• `/insights` - Spending analysis

❓ **Other Commands**
• `/help` - Show this message
• `/setup` - Re-run initial setup

💡 **Tips**
• I understand natural language - just tell me what you spent money on!
• I'll automatically categorize your expenses
• Get budget alerts when you're approaching limits
• Monthly reports help track your financial health
"""

    async def _handle_general_message(self, message: str, user_id: str) -> str:
        """Handle general messages, greetings, and unclear requests."""
        message_lower = message.lower()
        
        if any(greeting in message_lower for greeting in ["hi", "hello", "hey", "good morning", "good evening"]):
            return """
👋 **Hello! I'm your Personal Finance Assistant**

I'm here to help you track expenses, manage budgets, and gain insights into your spending habits.

**Quick Start:**
• Just tell me about your expenses: "Spent $25 on lunch"
• Check your balance: `/balance`
• Set up budgets: `/budget`
• Get help: `/help`

What would you like to do today? 💰
"""
        
        elif any(thanks in message_lower for thanks in ["thank", "thanks", "thx"]):
            return "🙏 You're welcome! Happy to help with your finances. Need anything else?"
        
        else:
            return """
🤔 I'm not sure what you'd like to do. Here are some things I can help with:

💸 **Log an expense**: "Spent $20 on groceries"
💰 **Check balance**: `/balance`
📊 **View reports**: `/report`
🎯 **Manage budgets**: `/budget`
❓ **Get help**: `/help`

Just let me know what you need! 😊
"""

    def get_user_state(self, user_id: str) -> Optional[str]:
        """Get current user state for external monitoring."""
        return self.user_states.get(user_id, UserState.NEW_USER).value if user_id in self.user_states else None