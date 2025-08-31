from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import re
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.tools.reasoning import ReasoningTools
from ..tools.excel_tools import ExcelFinanceManager
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)


class OnboardingAgent(Agent):
    """
    Specialized agent for user onboarding and initial setup.
    Guides users through balance setup and budget creation.
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
            name="OnboardingGuide",
            role="User Onboarding and Setup Specialist",
            markdown=True,
            show_tool_calls=True
        )
        
        self.excel_manager = excel_manager
        
    def _get_instructions(self) -> str:
        """Get onboarding agent instructions using GPT-5 best practices."""
        return f"""
<role>
You are a User Onboarding Specialist for a personal finance management system. Your primary goal is to guide new users through essential setup steps in a friendly, efficient manner.
</role>

<onboarding_flow>
1. **Welcome & Assessment**: Greet new users and assess their current setup status
2. **Balance Setup**: Guide users to enter their current account balance
3. **Budget Creation**: Help users establish budgets for expense categories
4. **Completion**: Confirm setup and introduce main features
</onboarding_flow>

<user_states>
- **new_user**: First interaction, needs complete setup
- **awaiting_balance**: User needs to provide current balance
- **awaiting_budgets**: User needs to create budgets for categories
- **active**: Setup complete, ready for normal operations
</user_states>

<categories_available>
{', '.join(settings.expense_categories)}
</categories_available>

<setup_guidelines>
**Balance Setup:**
- Ask for current account balance in {settings.default_currency}
- Accept various formats: "1500", "$1500", "1,500.00"
- Validate positive numbers only
- Provide reassurance about data privacy

**Budget Creation:**
- Guide users through category-by-category budget setting
- Suggest realistic budget amounts based on common patterns
- Allow users to skip categories they don't use
- Ensure total budgets don't exceed their comfort level
- Provide flexibility to adjust later
</setup_guidelines>

<interaction_principles>
- **Be Encouraging**: Make setup feel achievable, not overwhelming
- **Stay Focused**: Keep users on track through the onboarding flow
- **Provide Context**: Explain why each step matters for their financial health
- **Be Flexible**: Allow users to modify or skip optional steps
- **Celebrate Progress**: Acknowledge completion of each step
</interaction_principles>

<validation_rules>
- Balance must be a positive number
- Budget amounts must be positive numbers
- At least 3 categories should have budgets for meaningful tracking
- Total budgets shouldn't exceed 90% of income (if provided)
</validation_rules>

<response_format>
Use **clear formatting** with:
- 🎯 For goal/objective statements
- ✅ For completed steps
- 📝 For action items
- 💡 For tips and suggestions
- ⚠️ For important warnings
- 🎉 For celebrations and completions
</response_format>

<error_handling>
- Guide users to correct format for invalid inputs
- Provide specific examples for unclear responses
- Offer to restart steps if users get confused
- Never make users feel bad about mistakes
</error_handling>
"""

    async def process_onboarding_step(
        self,
        message: str,
        user_id: str,
        current_state: str
    ) -> str:
        """Process a single onboarding step based on current user state."""
        try:
            if current_state == "new_user":
                return await self._welcome_new_user()
                
            elif current_state == "awaiting_balance":
                return await self._process_balance_setup(message, user_id)
                
            elif current_state == "awaiting_budgets":
                return await self._process_budget_setup(message, user_id)
                
            else:
                return await self._handle_unexpected_state(current_state)
                
        except Exception as e:
            logger.error(f"Error processing onboarding step: {e}")
            return "❌ Something went wrong during setup. Let me help you restart this step."

    async def _welcome_new_user(self) -> str:
        """Welcome new users and start onboarding process."""
        return """
🎉 **Welcome to Your Personal Finance Tracker!**

I'm excited to help you take control of your finances. Before we start tracking expenses, let's set up your account with a quick 2-step process:

🎯 **Setup Steps:**
1. **Current Balance** - Tell me how much money you currently have
2. **Budget Creation** - Set spending limits for different categories

This will only take a couple of minutes and will make expense tracking much more powerful! 💪

📝 **Let's start with your current balance**

Please tell me your current account balance. You can say:
• "My balance is $2,500"
• "I have $1,200 in my account"  
• Just the number: "1500"

💡 *Don't worry - this information stays private and secure on your device.*

What's your current balance?
"""

    async def _process_balance_setup(self, message: str, user_id: str) -> str:
        """Process user's balance setup message."""
        try:
            # Extract balance amount from message
            balance = await self._extract_balance_amount(message)
            
            if balance is None:
                return """
🤔 I couldn't understand the balance amount. Let me help!

📝 **Please provide your balance in one of these formats:**
• "My balance is $1,500"
• "I have 2500 dollars"
• "1200.50"
• "$1,000"

What's your current account balance?
"""
            
            if balance < 0:
                return """
⚠️ Balance cannot be negative. 

📝 Please enter your current available balance as a positive number.
What's your current account balance?
"""
            
            # Save balance to Excel
            result = self.excel_manager.set_user_balance(balance)
            
            if not result.get("success", False):
                return f"""
❌ There was an issue saving your balance. Let me try to help.

Please try entering your balance again, or contact support if the problem persists.
What's your current account balance?
"""
            
            # Move to budget setup
            return f"""
✅ **Great! Balance set to ${balance:,.2f}**

🎯 **Now let's create your spending budgets**

Budgets help you:
• Stay on track with your financial goals
• Get alerts before overspending  
• See where your money goes each month

📝 I'll guide you through setting budgets for the categories you use most. You can always adjust these later!

**Available Categories:**
{self._format_categories_list()}

Let's start with the most common ones. **How much would you like to budget for Food & Dining each month?**

💡 *Tip: Most people spend 10-15% of their income on food. You can say "skip" for categories you don't use.*
"""
            
        except Exception as e:
            logger.error(f"Error processing balance setup: {e}")
            return "❌ There was an error processing your balance. Please try again."

    async def _extract_balance_amount(self, message: str) -> Optional[float]:
        """Extract balance amount from user message using AI parsing."""
        try:
            # First try simple regex patterns
            patterns = [
                r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,500.00 format
                r'(\d+(?:\.\d{2})?)',  # Simple decimal format
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, message.replace(',', ''))
                if matches:
                    try:
                        return float(matches[0].replace(',', ''))
                    except ValueError:
                        continue
            
            # Use AI for complex parsing
            extraction_prompt = f"""
<task>
Extract a balance amount from this user message.
</task>

<message>
"{message}"
</message>

<instructions>
- Look for monetary amounts, numbers, or balance indicators
- Return only the numeric value as a float
- Ignore negative numbers
- If no valid balance found, return "NONE"
</instructions>

<examples>
"My balance is $1,500" -> 1500.0
"I have 2500 dollars" -> 2500.0
"Current balance: 1,200.50" -> 1200.5
"No money" -> NONE
"I'm broke" -> NONE
</examples>

<output_format>
Return only the number (e.g., "1500.0") or "NONE"
</output_format>
"""
            
            response = await self.arun(extraction_prompt)
            response = response.strip()
            
            if response.upper() == "NONE":
                return None
                
            try:
                return float(response)
            except ValueError:
                return None
                
        except Exception as e:
            logger.error(f"Error extracting balance amount: {e}")
            return None

    async def _process_budget_setup(self, message: str, user_id: str) -> str:
        """Process budget setup messages with guided category-by-category approach."""
        try:
            # Get current budget setup progress
            budget_status = self.excel_manager.get_budget_setup_progress()
            
            # Parse the user's response
            budget_response = await self._parse_budget_response(message)
            
            if budget_response["action"] == "skip":
                return await self._handle_budget_skip(budget_status)
            elif budget_response["action"] == "set_amount":
                return await self._handle_budget_amount(budget_response, budget_status)
            elif budget_response["action"] == "complete":
                return await self._complete_budget_setup()
            else:
                return await self._handle_budget_clarification(budget_status)
                
        except Exception as e:
            logger.error(f"Error processing budget setup: {e}")
            return "❌ There was an error setting up your budget. Let me help you continue."

    async def _parse_budget_response(self, message: str) -> Dict[str, Any]:
        """Parse user's budget response to determine action and amount."""
        try:
            message_lower = message.lower().strip()
            
            # Check for skip/pass indicators
            if any(skip_word in message_lower for skip_word in ["skip", "pass", "next", "don't use", "not needed"]):
                return {"action": "skip"}
            
            # Check for completion indicators
            if any(complete_word in message_lower for complete_word in ["done", "finished", "complete", "that's all"]):
                return {"action": "complete"}
            
            # Try to extract budget amount
            amount = await self._extract_budget_amount(message)
            if amount is not None:
                return {"action": "set_amount", "amount": amount}
            
            return {"action": "unclear"}
            
        except Exception as e:
            logger.error(f"Error parsing budget response: {e}")
            return {"action": "unclear"}

    async def _extract_budget_amount(self, message: str) -> Optional[float]:
        """Extract budget amount from user message."""
        try:
            # Simple regex patterns for budget amounts
            patterns = [
                r'\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',  # $500.00 format
                r'(\d+)',  # Simple number
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, message.replace(',', ''))
                if matches:
                    try:
                        amount = float(matches[0].replace(',', ''))
                        if 0 < amount <= 10000:  # Reasonable budget range
                            return amount
                    except ValueError:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting budget amount: {e}")
            return None

    async def _handle_budget_amount(self, budget_response: Dict[str, Any], budget_status: Dict[str, Any]) -> str:
        """Handle setting a budget amount for the current category."""
        try:
            current_category = budget_status.get("current_category", "Food & Dining")
            amount = budget_response["amount"]
            
            # Save budget to Excel
            result = self.excel_manager.set_category_budget(current_category, amount)
            
            if not result.get("success", False):
                return f"❌ There was an issue setting your {current_category} budget. Please try again."
            
            # Move to next category or complete
            next_category = self._get_next_budget_category(budget_status)
            
            if next_category:
                return f"""
✅ **{current_category}: ${amount:,.2f}/month set!**

📝 **Next: How much for {next_category}?**

💡 *You can say "skip" if you don't use this category, or "done" if you want to finish setup.*
"""
            else:
                return await self._complete_budget_setup()
                
        except Exception as e:
            logger.error(f"Error handling budget amount: {e}")
            return "❌ Error setting budget amount. Please try again."

    async def _handle_budget_skip(self, budget_status: Dict[str, Any]) -> str:
        """Handle skipping a budget category."""
        current_category = budget_status.get("current_category", "Food & Dining")
        next_category = self._get_next_budget_category(budget_status)
        
        if next_category:
            return f"""
⏭️ **Skipped {current_category}**

📝 **Next: How much for {next_category}?**

💡 *Say "skip" to skip this one too, or "done" to finish setup.*
"""
        else:
            return await self._complete_budget_setup()

    async def _complete_budget_setup(self) -> str:
        """Complete the budget setup process."""
        try:
            # Mark user as fully onboarded
            self.excel_manager.mark_user_setup_complete()
            
            # Get summary of created budgets
            budgets = self.excel_manager.get_user_budgets()
            budget_summary = ""
            
            if budgets.get("success") and budgets.get("budgets"):
                budget_summary = "\n**Your Budgets:**\n"
                for budget in budgets["budgets"]:
                    budget_summary += f"• {budget['category']}: ${budget['amount']:,.2f}/month\n"
            
            return f"""
🎉 **Setup Complete! Welcome to your Finance Tracker!**

✅ Account balance set
✅ Budgets created
{budget_summary}

🚀 **You're ready to start tracking expenses!**

**How to use your tracker:**
• Just tell me about expenses: *"Spent $25 on lunch"*
• Check your balance: `/balance`
• View reports: `/report`
• Modify budgets: `/budget`

💡 **Pro tip:** I'll automatically categorize your expenses and alert you when you're approaching budget limits!

**Ready to log your first expense?** Just tell me what you spent money on! 💰

**Status:** onboarding_complete
"""
            
        except Exception as e:
            logger.error(f"Error completing budget setup: {e}")
            return "🎉 **Setup Complete!** You're ready to start tracking expenses. Just tell me what you spent money on!"

    def _format_categories_list(self) -> str:
        """Format the available categories in a readable list."""
        categories = settings.expense_categories
        formatted = ""
        for i, category in enumerate(categories, 1):
            formatted += f"{i}. {category}\n"
        return formatted.rstrip()

    def _get_next_budget_category(self, budget_status: Dict[str, Any]) -> Optional[str]:
        """Get the next category for budget setup."""
        # This is a simplified implementation
        # In production, track which categories have been set
        priority_categories = [
            "Food & Dining",
            "Transportation", 
            "Shopping",
            "Bills & Utilities",
            "Entertainment"
        ]
        
        current = budget_status.get("current_category", "")
        try:
            current_index = priority_categories.index(current)
            if current_index + 1 < len(priority_categories):
                return priority_categories[current_index + 1]
        except ValueError:
            return priority_categories[0] if priority_categories else None
        
        return None

    async def _handle_unexpected_state(self, state: str) -> str:
        """Handle unexpected onboarding states."""
        logger.warning(f"Unexpected onboarding state: {state}")
        return """
🤔 It looks like there was a mix-up in your setup process.

Let me help you get back on track! Would you like to:
• Complete your balance setup
• Set up your budgets  
• Restart the setup process

Just let me know what you'd like to do!
"""