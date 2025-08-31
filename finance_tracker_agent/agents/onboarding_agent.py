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
            print(f"🎓 [ONBOARDING] Processing step - State: {current_state}, Message: '{message}'")
            
            if current_state == "new_user":
                print(f"🆕 [ONBOARDING] Welcoming new user...")
                return await self._welcome_new_user()
                
            elif current_state == "awaiting_balance":
                print(f"💰 [ONBOARDING] Processing balance setup...")
                return await self._process_balance_setup(message, user_id)
                
            elif current_state == "awaiting_budgets":
                print(f"🎯 [ONBOARDING] Processing budget setup...")
                return await self._process_budget_setup(message, user_id)
                
            else:
                print(f"❓ [ONBOARDING] Unexpected state: {current_state}")
                return await self._handle_unexpected_state(current_state)
                
        except Exception as e:
            logger.error(f"Error processing onboarding step: {e}")
            print(f"❌ [ONBOARDING] ERROR in process_onboarding_step: {str(e)}")
            return "❌ Something went wrong during setup. Let me help you restart this step."

    async def _welcome_new_user(self) -> str:
        """Welcome new users and start onboarding process."""
        print(f"🎉 [ONBOARDING] Welcoming new user and transitioning to AWAITING_BALANCE")
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

**Status:** awaiting_balance
"""

    async def _process_balance_setup(self, message: str, user_id: str) -> str:
        """Process user's balance setup message."""
        try:
            print(f"💰 [ONBOARDING] Processing balance setup for message: '{message}'")
            
            # Extract balance amount from message
            balance = await self._extract_balance_amount(message)
            print(f"🔍 [ONBOARDING] Extracted balance: {balance}")
            
            if balance is None:
                print(f"❌ [ONBOARDING] Failed to extract balance from: '{message}'")
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
                print(f"❌ [ONBOARDING] Negative balance rejected: {balance}")
                return """
⚠️ Balance cannot be negative. 

📝 Please enter your current available balance as a positive number.
What's your current account balance?
"""
            
            print(f"💾 [ONBOARDING] Saving balance ${balance:,.2f} to Excel...")
            # Save balance to Excel
            result = self.excel_manager.set_user_balance(balance)
            print(f"💾 [EXCEL] Balance save result: {result}")
            
            if not result.get("success", False):
                print(f"❌ [ONBOARDING] Failed to save balance: {result.get('error', 'Unknown error')}")
                return f"""
❌ There was an issue saving your balance. Let me try to help.

Please try entering your balance again, or contact support if the problem persists.
What's your current account balance?
"""
            
            print(f"✅ [ONBOARDING] Balance ${balance:,.2f} saved successfully!")
            
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
            print(f"❌ [ONBOARDING] ERROR in balance setup: {str(e)}")
            return "❌ There was an error processing your balance. Please try again."

    async def _extract_balance_amount(self, message: str) -> Optional[float]:
        """Extract balance amount from user message using enhanced parsing."""
        try:
            print(f"🔍 [BALANCE_EXTRACT] Parsing message: '{message}'")
            
            # Clean the message for better parsing
            clean_message = message.replace(',', '').replace('$', '')
            print(f"🧹 [BALANCE_EXTRACT] Cleaned message: '{clean_message}'")
            
            # Enhanced regex patterns with debugging
            patterns = [
                r'(?:balance|have|is)\s+.*?(\d+(?:\.\d{1,2})?)',  # "balance is 1500"
                r'(\d+(?:\.\d{1,2})?)\s*(?:dollars?|bucks?|usd)?',  # "1500 dollars"
                r'(\d{1,6}(?:\.\d{1,2})?)',  # Any reasonable number
            ]
            
            for i, pattern in enumerate(patterns):
                print(f"🔍 [BALANCE_EXTRACT] Trying pattern {i+1}: {pattern}")
                matches = re.findall(pattern, clean_message, re.IGNORECASE)
                if matches:
                    print(f"✅ [BALANCE_EXTRACT] Pattern {i+1} found matches: {matches}")
                    for match in matches:
                        try:
                            balance = float(match)
                            if 0.01 <= balance <= 999999.99:  # Reasonable balance range
                                print(f"✅ [BALANCE_EXTRACT] Valid balance extracted: {balance}")
                                return balance
                            else:
                                print(f"❌ [BALANCE_EXTRACT] Balance out of range: {balance}")
                        except ValueError as ve:
                            print(f"❌ [BALANCE_EXTRACT] Float conversion failed: {ve}")
                            continue
                else:
                    print(f"❌ [BALANCE_EXTRACT] Pattern {i+1} no matches")
            
            # If regex fails, try simple number extraction
            print(f"🎯 [BALANCE_EXTRACT] Regex failed, trying simple number extraction...")
            numbers = re.findall(r'\d+(?:\.\d{1,2})?', clean_message)
            print(f"🔢 [BALANCE_EXTRACT] Found numbers: {numbers}")
            
            if numbers:
                for num_str in numbers:
                    try:
                        balance = float(num_str)
                        if 0.01 <= balance <= 999999.99:
                            print(f"✅ [BALANCE_EXTRACT] Simple extraction successful: {balance}")
                            return balance
                    except ValueError:
                        continue
            
            # Last resort: try to find any decimal number
            print(f"🔍 [BALANCE_EXTRACT] Final attempt - looking for any number...")
            final_pattern = r'(\d+(?:\.\d+)?)'
            final_matches = re.findall(final_pattern, message)
            print(f"🔍 [BALANCE_EXTRACT] Final pattern matches: {final_matches}")
            
            if final_matches:
                try:
                    balance = float(final_matches[0])
                    if balance > 0:
                        print(f"✅ [BALANCE_EXTRACT] Final attempt successful: {balance}")
                        return balance
                except ValueError:
                    pass
            
            print(f"❌ [BALANCE_EXTRACT] All extraction methods failed")
            return None
                
        except Exception as e:
            logger.error(f"Error extracting balance amount: {e}")
            print(f"❌ [BALANCE_EXTRACT] EXCEPTION: {str(e)}")
            return None

    async def _process_budget_setup(self, message: str, user_id: str) -> str:
        """Process budget setup messages with guided category-by-category approach."""
        try:
            print(f"🎯 [BUDGET_SETUP] Processing message: '{message}'")
            
            # Get current budget setup progress
            budget_status = self.excel_manager.get_budget_setup_progress()
            print(f"📊 [BUDGET_SETUP] Current progress: {budget_status}")
            
            # Parse the user's response
            budget_response = await self._parse_budget_response(message)
            print(f"🎯 [BUDGET_SETUP] Parsed response: {budget_response}")
            
            if budget_response["action"] == "skip":
                print(f"⏭️ [BUDGET_SETUP] User wants to skip current category")
                return await self._handle_budget_skip(budget_status)
            elif budget_response["action"] == "set_amount":
                print(f"💰 [BUDGET_SETUP] User setting amount: {budget_response.get('amount')}")
                return await self._handle_budget_amount(budget_response, budget_status)
            elif budget_response["action"] == "complete":
                print(f"✅ [BUDGET_SETUP] User wants to complete setup")
                return await self._complete_budget_setup()
            elif budget_response["action"] == "question":
                print(f"❓ [BUDGET_SETUP] User is asking a question")
                return await self._handle_budget_question(budget_status, message)
            else:
                print(f"❓ [BUDGET_SETUP] Need clarification from user")
                return await self._handle_budget_clarification(budget_status)
                
        except Exception as e:
            logger.error(f"Error processing budget setup: {e}")
            print(f"❌ [BUDGET_SETUP] ERROR: {str(e)}")
            return "❌ There was an error setting up your budget. Let me help you continue."

    async def _parse_budget_response(self, message: str) -> Dict[str, Any]:
        """Parse user's budget response to determine action and amount."""
        try:
            message_lower = message.lower().strip()
            print(f"🎯 [BUDGET_PARSE] Parsing message: '{message_lower}'")
            
            # Check for skip/pass indicators (expanded list)
            skip_indicators = [
                "skip", "pass", "next", "don't use", "not needed", "none", "no", "0",
                "don't want", "not interested", "skip this", "pass on this", "no budget"
            ]
            
            if any(skip_word in message_lower for skip_word in skip_indicators):
                print(f"⏭️ [BUDGET_PARSE] Detected skip command")
                return {"action": "skip"}
            
            # Check for completion indicators (expanded list)
            complete_indicators = [
                "done", "finished", "complete", "that's all", "finish", "end", 
                "no more", "all done", "i'm done", "that's enough", "enough", "stop"
            ]
            
            if any(complete_word in message_lower for complete_word in complete_indicators):
                print(f"✅ [BUDGET_PARSE] Detected completion command")
                return {"action": "complete"}
            
            # Try to extract budget amount
            amount = await self._extract_budget_amount(message)
            if amount is not None:
                print(f"💰 [BUDGET_PARSE] Extracted budget amount: ${amount}")
                return {"action": "set_amount", "amount": amount}
            
            # Check if user is asking questions or being unclear
            question_indicators = ["what", "how", "why", "which", "help", "?"]
            if any(q in message_lower for q in question_indicators):
                print(f"❓ [BUDGET_PARSE] User seems to be asking a question")
                return {"action": "question"}
            
            print(f"❓ [BUDGET_PARSE] Message unclear, needs clarification")
            return {"action": "unclear"}
            
        except Exception as e:
            logger.error(f"Error parsing budget response: {e}")
            print(f"❌ [BUDGET_PARSE] ERROR: {str(e)}")
            return {"action": "unclear"}

    async def _extract_budget_amount(self, message: str) -> Optional[float]:
        """Extract budget amount from user message."""
        try:
            print(f"💰 [BUDGET_EXTRACT] Extracting amount from: '{message}'")
            
            # Clean the message for better parsing
            clean_message = message.replace(',', '').replace('$', '').strip()
            print(f"🧹 [BUDGET_EXTRACT] Cleaned message: '{clean_message}'")
            
            # Enhanced regex patterns with debugging
            patterns = [
                r'(?:budget|spend|allow)\s+.*?(\d+(?:\.\d{1,2})?)',  # "budget 500"
                r'(\d+(?:\.\d{1,2})?)\s*(?:dollars?|bucks?|per month|monthly)?',  # "500 dollars"
                r'(\d{1,4}(?:\.\d{1,2})?)',  # Any reasonable number
            ]
            
            for i, pattern in enumerate(patterns):
                print(f"💰 [BUDGET_EXTRACT] Trying pattern {i+1}: {pattern}")
                matches = re.findall(pattern, clean_message, re.IGNORECASE)
                if matches:
                    print(f"✅ [BUDGET_EXTRACT] Pattern {i+1} found matches: {matches}")
                    for match in matches:
                        try:
                            amount = float(match)
                            if 1 <= amount <= 50000:  # Reasonable budget range
                                print(f"✅ [BUDGET_EXTRACT] Valid budget amount: ${amount}")
                                return amount
                            else:
                                print(f"❌ [BUDGET_EXTRACT] Amount out of range: {amount}")
                        except ValueError as ve:
                            print(f"❌ [BUDGET_EXTRACT] Float conversion failed: {ve}")
                            continue
                else:
                    print(f"❌ [BUDGET_EXTRACT] Pattern {i+1} no matches")
            
            # Final attempt: find any number
            print(f"🎯 [BUDGET_EXTRACT] Final attempt - looking for any number...")
            numbers = re.findall(r'\d+(?:\.\d+)?', clean_message)
            print(f"🔢 [BUDGET_EXTRACT] Found numbers: {numbers}")
            
            if numbers:
                for num_str in numbers:
                    try:
                        amount = float(num_str)
                        if 1 <= amount <= 50000:
                            print(f"✅ [BUDGET_EXTRACT] Final attempt successful: ${amount}")
                            return amount
                    except ValueError:
                        continue
            
            print(f"❌ [BUDGET_EXTRACT] All extraction methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting budget amount: {e}")
            print(f"❌ [BUDGET_EXTRACT] EXCEPTION: {str(e)}")
            return None

    async def _handle_budget_amount(self, budget_response: Dict[str, Any], budget_status: Dict[str, Any]) -> str:
        """Handle setting a budget amount for the current category."""
        try:
            current_category = budget_status.get("current_category", "Food & Dining")
            amount = budget_response["amount"]
            
            print(f"💰 [BUDGET_AMOUNT] Setting ${amount} for {current_category}")
            
            # Save budget to Excel
            result = self.excel_manager.set_category_budget(current_category, amount)
            print(f"💾 [BUDGET_AMOUNT] Excel save result: {result}")
            
            if not result.get("success", False):
                print(f"❌ [BUDGET_AMOUNT] Failed to save budget: {result.get('error')}")
                return f"❌ There was an issue setting your {current_category} budget. Please try again."
            
            # Update progress tracking
            configured_count = budget_status.get("configured_count", 0) + 1
            print(f"📊 [BUDGET_AMOUNT] Budget #{configured_count} configured")
            
            # Check if we have enough budgets (minimum 2, or user can say done)
            if configured_count >= 2:
                print(f"✅ [BUDGET_AMOUNT] Minimum budgets met, offering completion")
                # Move to next category or complete
                next_category = self._get_next_budget_category(budget_status, current_category)
                
                if next_category:
                    return f"""
✅ **{current_category}: ${amount:,.2f}/month set!** ({configured_count} budgets created)

📝 **Next: How much for {next_category}?**

💡 *You can say "skip" if you don't use this category, or "done" if you want to finish setup now.*
"""
                else:
                    print(f"🎯 [BUDGET_AMOUNT] No more priority categories, completing setup")
                    return await self._complete_budget_setup()
            else:
                # Need at least 2 budgets before allowing completion
                next_category = self._get_next_budget_category(budget_status, current_category)
                return f"""
✅ **{current_category}: ${amount:,.2f}/month set!** ({configured_count}/2 minimum)

📝 **Next: How much for {next_category}?**

💡 *You can say "skip" if you don't use this category. We need at least 2 budgets before finishing setup.*
"""
                
        except Exception as e:
            logger.error(f"Error handling budget amount: {e}")
            print(f"❌ [BUDGET_AMOUNT] ERROR: {str(e)}")
            return "❌ Error setting budget amount. Please try again."

    async def _handle_budget_skip(self, budget_status: Dict[str, Any]) -> str:
        """Handle skipping a budget category."""
        try:
            current_category = budget_status.get("current_category", "Food & Dining")
            configured_count = budget_status.get("configured_count", 0)
            
            print(f"⏭️ [BUDGET_SKIP] Skipping {current_category} (current count: {configured_count})")
            
            # Get next category
            next_category = self._get_next_budget_category(budget_status, current_category)
            
            if next_category:
                if configured_count >= 2:
                    # User has minimum budgets, can complete if they want
                    return f"""
⏭️ **Skipped {current_category}**

📝 **Next: How much for {next_category}?**

💡 *Say "skip" to skip this category too, or "done" to finish setup with your {configured_count} budgets.*
"""
                else:
                    # Still need more budgets
                    return f"""
⏭️ **Skipped {current_category}**

📝 **Next: How much for {next_category}?**

💡 *Say "skip" to skip this category too. We need at least 2 budgets total (currently have {configured_count}).*
"""
            else:
                # No more categories, check if we have minimum
                if configured_count >= 2:
                    print(f"✅ [BUDGET_SKIP] No more categories, completing with {configured_count} budgets")
                    return await self._complete_budget_setup()
                else:
                    print(f"❌ [BUDGET_SKIP] Ran out of categories but only have {configured_count} budgets")
                    return f"""
⏭️ **Skipped {current_category}**

❌ We've gone through all the main categories, but you only have {configured_count} budget(s) set up.

**Let's go back to some categories you might have skipped:**
• Transportation - for gas, parking, rides
• Shopping - for general purchases
• Entertainment - for movies, dining out

**Please set a budget amount for any of these, or type "done" if you want to continue with just {configured_count} budget(s).**
"""
                    
        except Exception as e:
            logger.error(f"Error handling budget skip: {e}")
            print(f"❌ [BUDGET_SKIP] ERROR: {str(e)}")
            return "❌ Error processing skip. Let's continue with the next category."

    async def _complete_budget_setup(self) -> str:
        """Complete the budget setup process."""
        try:
            print(f"🎉 [COMPLETE_SETUP] Completing budget setup and marking user as active")
            
            # Mark user as fully onboarded
            completion_result = self.excel_manager.mark_user_setup_complete()
            print(f"💾 [COMPLETE_SETUP] Setup completion result: {completion_result}")
            
            # Get summary of created budgets
            budgets = self.excel_manager.get_user_budgets()
            budget_count = len(budgets.get("budgets", [])) if budgets.get("success") else 0
            
            budget_summary = ""
            
            if budgets.get("success") and budgets.get("budgets"):
                budget_summary = "\n**Your Budgets:**\n"
                for budget in budgets["budgets"]:
                    budget_summary += f"• {budget['category']}: ${budget['amount']:,.2f}/month\n"
            
            print(f"✅ [COMPLETE_SETUP] Setup completed with {budget_count} budgets")
            
            return f"""
🎉 **Setup Complete! Welcome to your Finance Tracker!**

✅ Account balance set
✅ {budget_count} budgets created
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
            print(f"❌ [COMPLETE_SETUP] ERROR: {str(e)}")
            return "🎉 **Setup Complete!** You're ready to start tracking expenses. Just tell me what you spent money on!"

    def _format_categories_list(self) -> str:
        """Format the available categories in a readable list."""
        categories = settings.expense_categories
        formatted = ""
        for i, category in enumerate(categories, 1):
            formatted += f"{i}. {category}\n"
        return formatted.rstrip()

    def _get_next_budget_category(self, budget_status: Dict[str, Any], current_category: Optional[str] = None) -> Optional[str]:
        """Get the next category for budget setup."""
        try:
            priority_categories = [
                "Food & Dining",
                "Transportation", 
                "Shopping",
                "Bills & Utilities",
                "Entertainment"
            ]
            
            # Get already configured categories to skip them
            configured_categories = budget_status.get("configured_categories", [])
            current = current_category or budget_status.get("current_category", "")
            
            print(f"🎯 [NEXT_CATEGORY] Current: '{current}', Configured: {configured_categories}")
            
            # Find current index
            try:
                current_index = priority_categories.index(current)
                start_index = current_index + 1
            except ValueError:
                # Current category not in list, start from beginning
                start_index = 0
            
            # Find next unconfigured category
            for i in range(start_index, len(priority_categories)):
                category = priority_categories[i]
                if category not in configured_categories:
                    print(f"🎯 [NEXT_CATEGORY] Next category: {category}")
                    return category
            
            # No more unconfigured priority categories
            print(f"🎯 [NEXT_CATEGORY] No more priority categories available")
            return None
            
        except Exception as e:
            logger.error(f"Error getting next budget category: {e}")
            print(f"❌ [NEXT_CATEGORY] ERROR: {str(e)}")
            return None

    async def _handle_budget_clarification(self, budget_status: Dict[str, Any]) -> str:
        """Handle unclear budget responses by asking for clarification."""
        try:
            current_category = budget_status.get("current_category", "Food & Dining")
            configured_count = budget_status.get("configured_count", 0)
            
            print(f"❓ [BUDGET_CLARIFY] Need clarification for {current_category}")
            
            return f"""
❓ I didn't understand your response for **{current_category}**.

**Please tell me:**
• A dollar amount (e.g., "200", "$300", "500 dollars")
• "skip" if you don't want to budget for this category
• "done" if you want to finish setup now ({configured_count} budgets created)

**How much would you like to budget for {current_category} each month?**
"""
        except Exception as e:
            logger.error(f"Error handling budget clarification: {e}")
            print(f"❌ [BUDGET_CLARIFY] ERROR: {str(e)}")
            return "❓ I didn't understand your response. Please try again with a dollar amount or say 'skip'."

    async def _handle_budget_question(self, budget_status: Dict[str, Any], message: str) -> str:
        """Handle questions during budget setup."""
        try:
            current_category = budget_status.get("current_category", "Food & Dining")
            configured_count = budget_status.get("configured_count", 0)
            message_lower = message.lower()
            
            print(f"❓ [BUDGET_QUESTION] Handling question about {current_category}: '{message}'")
            
            # Common questions and responses
            if any(word in message_lower for word in ["how much", "what amount", "typical", "average", "recommend"]):
                return f"""
💡 **Budget suggestions for {current_category}:**

• **Conservative**: $100-200/month
• **Moderate**: $300-500/month  
• **Higher**: $600+/month

**Tips:**
• Look at your last few months' spending in this category
• Start lower - you can always adjust later
• Consider your total income and other expenses

**What amount works for your {current_category} budget?**
"""
            
            elif any(word in message_lower for word in ["skip", "optional", "need"]):
                return f"""
💡 **About {current_category} budgets:**

You can definitely skip categories you don't use much. We just need at least 2 budgets total to get started.

**Current progress:** {configured_count} budgets created

**Options:**
• Set an amount: "300" or "$300"
• Skip this category: "skip"
• Finish setup: "done" (if you have 2+ budgets)

**What would you like to do with {current_category}?**
"""
            
            else:
                # Generic help response
                return f"""
❓ **Budget Setup Help:**

For **{current_category}**, you can:
• Enter a dollar amount: "200", "$300", "500 dollars"
• Skip this category: "skip"
• Finish setup: "done" (you have {configured_count} budgets so far)

**Common {current_category} expenses might include:**
{self._get_category_examples(current_category)}

**What amount would you like to budget for {current_category}?**
"""
                
        except Exception as e:
            logger.error(f"Error handling budget question: {e}")
            print(f"❌ [BUDGET_QUESTION] ERROR: {str(e)}")
            return "💡 You can enter a dollar amount, say 'skip', or 'done' to finish setup."

    def _get_category_examples(self, category: str) -> str:
        """Get examples for a budget category."""
        examples = {
            "Food & Dining": "• Groceries, restaurants, coffee, takeout",
            "Transportation": "• Gas, parking, public transit, rideshares", 
            "Shopping": "• Clothes, electronics, household items",
            "Bills & Utilities": "• Rent, utilities, phone, insurance",
            "Entertainment": "• Movies, subscriptions, dining out, hobbies"
        }
        return examples.get(category, "• Various expenses in this category")

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