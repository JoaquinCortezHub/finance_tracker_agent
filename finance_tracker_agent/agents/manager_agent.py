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
            print(f"\n🤖 [MANAGER] Processing message from user {user_id}: '{message}'")
            
            # Initialize user state if new
            if user_id not in self.user_states:
                print(f"🆕 [MANAGER] New user detected, initializing...")
                await self._initialize_new_user(user_id)
            
            current_state = self.user_states[user_id]
            print(f"👤 [MANAGER] User {user_id} current state: {current_state.value}")
            
            # Handle onboarding flow
            if current_state != UserState.ACTIVE:
                print(f"📝 [MANAGER] Delegating to ONBOARDING agent (state: {current_state.value})")
                response = await self._handle_onboarding_message(
                    message, user_id, chat_id, current_state
                )
                # Check if state changed after onboarding step
                new_state = self.user_states.get(user_id, current_state)
                if new_state != current_state:
                    print(f"🔄 [MANAGER] User state changed: {current_state.value} → {new_state.value}")
                print(f"✅ [MANAGER] Onboarding response ready ({len(response)} chars)")
                return response
            
            # For active users, classify intent and delegate
            print(f"🎯 [MANAGER] User is ACTIVE, classifying intent...")
            intent = await self._classify_intent(message, user_id)
            print(f"🎯 [MANAGER] Intent classified as: {intent}")
            response = await self._delegate_to_agent(message, intent, user_id, chat_id)
            print(f"✅ [MANAGER] Specialized agent response ready ({len(response)} chars)")
            return response
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            print(f"❌ [MANAGER] ERROR: {str(e)}")
            return "❌ I encountered an error processing your request. Please try again in a moment."

    async def _initialize_new_user(self, user_id: str) -> None:
        """Initialize a new user and determine their onboarding needs."""
        try:
            print(f"🔍 [MANAGER] Checking existing user data...")
            # Check if user has existing data
            user_data = self.excel_manager.get_user_setup_status()
            print(f"📊 [MANAGER] User setup status: {user_data}")
            
            if user_data.get("has_balance") and user_data.get("has_budgets"):
                self.user_states[user_id] = UserState.ACTIVE
                print(f"🏆 [MANAGER] User {user_id} recognized as RETURNING user (ACTIVE state)")
                logger.info(f"User {user_id} recognized as returning user")
            else:
                self.user_states[user_id] = UserState.NEW_USER
                print(f"🆕 [MANAGER] User {user_id} set to NEW_USER (needs onboarding)")
                logger.info(f"New user {user_id} initialized for onboarding")
                
            # Initialize conversation context
            self.conversation_context[user_id] = []
            
        except Exception as e:
            logger.error(f"Failed to initialize user {user_id}: {e}")
            print(f"❌ [MANAGER] Error initializing user, defaulting to NEW_USER: {e}")
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
            print(f"🎓 [ONBOARDING] Processing step for state: {current_state.value}")
            
            response = await self.onboarding_agent.process_onboarding_step(
                message=message,
                user_id=user_id,
                current_state=current_state.value
            )
            
            print(f"📝 [ONBOARDING] Response received, checking for state transitions...")
            
            # Check Excel state to determine actual progress (more reliable than text parsing)
            user_setup_status = self.excel_manager.get_user_setup_status()
            print(f"💾 [EXCEL] Current setup status: {user_setup_status}")
            
            # Update user state based on actual data in Excel AND response content
            old_state = current_state
            
            # Check for special state transition indicators in response
            if "awaiting_balance" in response.lower():
                self.user_states[user_id] = UserState.AWAITING_BALANCE
                print(f"🎯 [MANAGER] Response indicates → AWAITING_BALANCE")
            elif user_setup_status.get("setup_complete", False):
                self.user_states[user_id] = UserState.ACTIVE
                print(f"🎉 [MANAGER] User {user_id} completed onboarding → ACTIVE")
                logger.info(f"User {user_id} completed onboarding")
            elif user_setup_status.get("has_balance", False) and not user_setup_status.get("has_budgets", False):
                self.user_states[user_id] = UserState.AWAITING_BUDGETS
                print(f"💰 [MANAGER] User {user_id} has balance → AWAITING_BUDGETS")
            elif not user_setup_status.get("has_balance", False) and current_state == UserState.NEW_USER:
                # After welcome message, transition to awaiting balance
                self.user_states[user_id] = UserState.AWAITING_BALANCE
                print(f"⏳ [MANAGER] New user welcomed → AWAITING_BALANCE")
            else:
                # Keep current state if no clear transition
                print(f"🔄 [MANAGER] User {user_id} staying in state: {current_state.value}")
            
            # Log state transitions
            new_state = self.user_states[user_id]
            if new_state != old_state:
                print(f"🔄 [STATE] {user_id}: {old_state.value} → {new_state.value}")
                
            return response
            
        except Exception as e:
            logger.error(f"Error handling onboarding for user {user_id}: {e}")
            print(f"❌ [ONBOARDING] ERROR: {str(e)}")
            return "❌ There was an issue with your setup. Let me help you start over."

    async def _classify_intent(self, message: str, user_id: str) -> str:
        """Classify user message intent using hybrid approach (keywords + AI fallback)."""
        try:
            print(f"🎯 [INTENT] Classifying message: '{message}'")
            message_lower = message.lower().strip()
            
            # First, try keyword-based classification (faster and more reliable)
            intent = self._classify_intent_keywords(message_lower)
            if intent != "UNCLEAR":
                print(f"🎯 [INTENT] Keyword classification: {intent}")
                return intent
            
            # If keywords fail, try AI classification with better prompting
            print(f"🎯 [INTENT] Keywords unclear, trying AI classification...")
            ai_intent = await self._classify_intent_ai(message)
            print(f"🎯 [INTENT] AI classification: {ai_intent}")
            
            return ai_intent
            
        except Exception as e:
            logger.error(f"Failed to classify intent: {e}")
            print(f"❌ [INTENT] ERROR: {str(e)}")
            return "GENERAL"

    def _classify_intent_keywords(self, message_lower: str) -> str:
        """Fast keyword-based intent classification."""
        try:
            print(f"🔍 [KEYWORDS] Analyzing: '{message_lower}'")
            
            # Expense indicators (highest priority)
            expense_keywords = [
                "spent", "paid", "bought", "cost", "expense", "purchase", "transaction",
                "$", "dollars", "money", "bill", "receipt", "lunch", "dinner", 
                "gas", "groceries", "coffee", "shopping", "restaurant"
            ]
            
            # Budget indicators
            budget_keywords = [
                "budget", "limit", "allowance", "allocation", "set budget", 
                "increase budget", "decrease budget", "modify budget", "change budget"
            ]
            
            # Balance/Summary indicators  
            balance_keywords = [
                "balance", "total", "summary", "how much", "spent so far",
                "current spending", "month total", "spending summary"
            ]
            
            # Insights/Report indicators
            insights_keywords = [
                "report", "analysis", "insights", "trends", "patterns", 
                "monthly report", "spending report", "financial report", "breakdown"
            ]
            
            # Help indicators
            help_keywords = [
                "help", "commands", "what can you", "how do i", "instructions",
                "guide", "tutorial", "features", "capabilities"
            ]
            
            # Check expense first (most common)
            if any(kw in message_lower for kw in expense_keywords):
                print(f"✅ [KEYWORDS] Detected EXPENSE")
                return "EXPENSE"
                
            # Check budget
            if any(kw in message_lower for kw in budget_keywords):
                print(f"✅ [KEYWORDS] Detected BUDGET")
                return "BUDGET"
                
            # Check balance/summary
            if any(kw in message_lower for kw in balance_keywords):
                print(f"✅ [KEYWORDS] Detected BALANCE")
                return "BALANCE"
                
            # Check insights/reports
            if any(kw in message_lower for kw in insights_keywords):
                print(f"✅ [KEYWORDS] Detected INSIGHTS")
                return "INSIGHTS"
                
            # Check help
            if any(kw in message_lower for kw in help_keywords):
                print(f"✅ [KEYWORDS] Detected HELP")
                return "HELP"
            
            print(f"❓ [KEYWORDS] No clear match found")
            return "UNCLEAR"
            
        except Exception as e:
            logger.error(f"Error in keyword classification: {e}")
            print(f"❌ [KEYWORDS] ERROR: {str(e)}")
            return "UNCLEAR"

    async def _classify_intent_ai(self, message: str) -> str:
        """AI-powered intent classification with improved prompting."""
        try:
            classification_prompt = f"""
You are an expert at understanding user intent for personal finance apps.

Analyze this message and determine the user's primary intent:

Message: "{message}"

Intent Options:
- EXPENSE: User wants to log/record a spending transaction
- BUDGET: User wants to manage, check, or modify budgets  
- BALANCE: User wants to see current spending totals or summaries
- INSIGHTS: User wants reports, analysis, or spending insights
- HELP: User needs assistance or wants to know available commands
- GENERAL: Greetings, small talk, or unclear requests

Examples:
- "I spent 25 dollars on lunch" → EXPENSE
- "What's my food budget?" → BUDGET  
- "How much have I spent this month?" → BALANCE
- "Show me my spending report" → INSIGHTS
- "What commands are available?" → HELP
- "Hello there" → GENERAL

Respond with only the intent name (e.g., "EXPENSE").
"""
            
            response = await self.arun(classification_prompt)
            intent = response.strip().upper()
            
            # Validate intent
            valid_intents = ["EXPENSE", "BUDGET", "INSIGHTS", "BALANCE", "HELP", "GENERAL"]
            if intent not in valid_intents:
                print(f"❌ [AI_INTENT] Invalid intent returned: {intent}, defaulting to GENERAL")
                intent = "GENERAL"
            
            return intent
            
        except Exception as e:
            logger.error(f"AI intent classification failed: {e}")
            print(f"❌ [AI_INTENT] ERROR: {str(e)}")
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
            print(f"🎯 [DELEGATE] Routing {intent} intent to specialized agent")
            
            if intent == "EXPENSE":
                print(f"💸 [DELEGATE] → EXPENSE agent")
                return await self.expense_agent.process_expense_message(message)
                
            elif intent == "BUDGET":
                print(f"🎯 [DELEGATE] → BUDGET agent")
                return await self.budget_agent.process_budget_command(message)
                
            elif intent == "INSIGHTS":
                print(f"📊 [DELEGATE] → INSIGHTS agent")
                return await self.insights_agent.generate_monthly_report()
                
            elif intent == "BALANCE":
                print(f"💰 [DELEGATE] → Balance summary")
                return await self._get_balance_summary()
                
            elif intent == "HELP":
                print(f"❓ [DELEGATE] → Help message")
                return self._get_help_message()
                
            else:  # GENERAL or unknown
                print(f"💬 [DELEGATE] → General handler")
                return await self._handle_general_message(message, user_id, intent)
                
        except Exception as e:
            logger.error(f"Error delegating to agent for intent {intent}: {e}")
            print(f"❌ [DELEGATE] ERROR with {intent}: {str(e)}")
            
            # Provide helpful fallback based on intent
            if intent == "EXPENSE":
                return "❌ I had trouble logging your expense. Please try: 'I spent $25 on lunch'"
            elif intent == "BUDGET":
                return "❌ I had trouble with your budget request. Please try: 'What's my food budget?' or 'Set food budget to $400'"
            elif intent == "BALANCE":
                return "❌ I had trouble getting your balance. Please try again or contact support."
            else:
                return "❌ I had trouble processing your request. Please try rephrasing or type 'help' for available commands."

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

    async def _handle_general_message(self, message: str, user_id: str, intent: str) -> str:
        """Handle general messages with loop prevention and context awareness."""
        try:
            message_lower = message.lower().strip()
            print(f"💬 [GENERAL] Handling general message: '{message_lower}'")
            
            # Track conversation context to prevent loops
            context = self.conversation_context.get(user_id, [])
            recent_responses = [msg.get("response_type") for msg in context[-3:]]  # Last 3 messages
            
            print(f"🔍 [GENERAL] Recent response types: {recent_responses}")
            
            # Detect greeting loops
            if recent_responses.count("greeting") >= 2:
                print(f"🔄 [GENERAL] Loop detected! Redirecting to concrete help")
                return """
🔄 **I notice we're going in circles!** Let me be more specific about how I can help:

**Try one of these exact phrases:**
• "I spent 25 dollars on lunch" (to log an expense)
• "How much have I spent this month?" (to check balance)
• "Set food budget to 400" (to set a budget)
• "Show me my spending report" (to get insights)

**Or tell me what you're trying to accomplish and I'll guide you step by step!** 💪
"""
            
            # Handle specific message types
            if any(greeting in message_lower for greeting in ["hi", "hello", "hey", "good morning", "good evening"]):
                print(f"👋 [GENERAL] Greeting detected")
                # Add to context
                self._add_to_context(user_id, message, "greeting")
                
                return """
👋 **Hello! I'm your Personal Finance Assistant**

I'm here to help you track expenses, manage budgets, and gain insights into your spending habits.

**Most common tasks:**
• **Log expense**: "I spent $25 on lunch"
• **Check spending**: "How much have I spent this month?"
• **Set budget**: "Set food budget to $400"

**What would you like to do?** (Just tell me naturally!)
"""
            
            elif any(thanks in message_lower for thanks in ["thank", "thanks", "thx"]):
                print(f"🙏 [GENERAL] Thanks detected")
                self._add_to_context(user_id, message, "thanks")
                return "🙏 You're welcome! Need help with anything else? Just tell me what you want to do!"
            
            elif any(unclear in message_lower for unclear in ["what", "how", "help", "confused", "don't understand"]):
                print(f"❓ [GENERAL] User seems confused, providing specific help")
                self._add_to_context(user_id, message, "confused")
                
                return """
💡 **Let me help you get started!**

**Here are the exact things you can say:**

💸 **To log expenses** (most common):
• "I spent 25 dollars on lunch"
• "Paid $40 for gas"
• "Coffee was $4.50"

💰 **To check your spending**:
• "How much have I spent this month?"
• "What's my balance?"

🎯 **To manage budgets**:
• "Set food budget to $400"
• "What's my food budget?"

**Just pick one and try it!** I'll guide you from there. 😊
"""
            
            else:
                print(f"🤔 [GENERAL] Unclear message, providing helpful suggestions")
                self._add_to_context(user_id, message, "unclear")
                
                # Try to be more helpful by analyzing the message
                response = self._provide_contextual_help(message_lower)
                return response
                
        except Exception as e:
            logger.error(f"Error handling general message: {e}")
            print(f"❌ [GENERAL] ERROR: {str(e)}")
            return "❌ I'm having trouble understanding. Try typing 'help' or tell me specifically what you want to do."

    def _add_to_context(self, user_id: str, message: str, response_type: str) -> None:
        """Add message to conversation context for loop detection."""
        try:
            if user_id not in self.conversation_context:
                self.conversation_context[user_id] = []
            
            self.conversation_context[user_id].append({
                "message": message,
                "response_type": response_type,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep only last 10 messages to prevent memory bloat
            self.conversation_context[user_id] = self.conversation_context[user_id][-10:]
            
        except Exception as e:
            logger.error(f"Error adding to context: {e}")

    def _provide_contextual_help(self, message_lower: str) -> str:
        """Provide contextual help based on message content."""
        try:
            # Look for partial matches that might indicate intent
            if any(word in message_lower for word in ["money", "cost", "price", "buy", "purchase"]):
                return """
💡 **It sounds like you might want to log an expense!**

**Try saying:**
• "I spent $[amount] on [item]"
• For example: "I spent 25 dollars on lunch"

**Or if you want to check spending:**
• "How much have I spent this month?"

Which one sounds right? 🤔
"""
            
            elif any(word in message_lower for word in ["budget", "limit", "allowance"]):
                return """
💡 **It sounds like you want to work with budgets!**

**Try saying:**
• "Set [category] budget to $[amount]"
• For example: "Set food budget to 400"
• Or: "What's my food budget?"

**Want to see all your budgets?**
• "Show me my budgets"

Which one would help? 🎯
"""
            
            else:
                return """
🤔 **I'm not quite sure what you need, but here are the main things I can do:**

💸 **Track expenses**: "I spent $25 on lunch"
💰 **Check balance**: "How much have I spent?"
🎯 **Manage budgets**: "Set food budget to $400"
📊 **Generate reports**: "Show me my spending report"

**Just tell me what you want to accomplish!** I'll help you get there. 😊
"""
                
        except Exception as e:
            logger.error(f"Error providing contextual help: {e}")
            return "💡 Try saying something like 'I spent $25 on lunch' or 'How much have I spent this month?'"

    def get_user_state(self, user_id: str) -> Optional[str]:
        """Get current user state for external monitoring."""
        return self.user_states.get(user_id, UserState.NEW_USER).value if user_id in self.user_states else None