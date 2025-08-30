from typing import Dict, Any, Optional, List
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


class ExpenseTrackingAgent(Agent):
    """Agent specialized in tracking and categorizing expenses."""
    
    def __init__(self, excel_manager: ExcelFinanceManager):
        # Choose model based on available API keys
        if settings.anthropic_api_key:
            model = Claude(id="claude-sonnet-4-20250514", api_key=settings.anthropic_api_key)
        elif settings.openai_api_key:
            model = OpenAIChat(id="gpt-4", api_key=settings.openai_api_key)
        else:
            raise ValueError("No API key provided for AI model")
        
        super().__init__(
            model=model,
            tools=[ReasoningTools(add_instructions=True)],
            instructions=self._get_instructions(),
            name="ExpenseTracker",
            role="Financial Expense Tracking Assistant",
            markdown=True,
            show_tool_calls=True
        )
        
        self.excel_manager = excel_manager
        self.expense_patterns = self._compile_expense_patterns()
        self.category_mapping = self._get_category_mapping()
    
    def _get_instructions(self) -> str:
        """Get agent instructions."""
        return f"""
You are an expert financial expense tracking assistant. Your primary responsibilities are:

1. **Expense Extraction**: Parse natural language messages to extract expense information
   - Amount (in {settings.default_currency})
   - Description/merchant
   - Category (from predefined list)
   - Payment method (if mentioned)

2. **Expense Categorization**: Automatically categorize expenses into these categories:
   {', '.join(settings.expense_categories)}

3. **Data Validation**: Ensure extracted data is accurate and complete
   - Verify amounts are positive numbers
   - Standardize descriptions
   - Map similar merchants/descriptions consistently

4. **User Communication**: Provide clear, helpful responses about:
   - Successful expense logging
   - Budget impact warnings
   - Categorization explanations
   - Spending patterns

**Important Rules:**
- Always extract the most specific description possible
- Use consistent categorization logic
- Provide budget impact feedback
- Be conversational but concise
- Handle ambiguous input by asking for clarification

**Response Format:**
- Use emojis for visual clarity
- Provide spending insights when relevant
- Alert on budget concerns
- Suggest improvements when appropriate

Categories available: {', '.join(settings.expense_categories)}
"""
    
    def _compile_expense_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for expense extraction."""
        patterns = [
            # "Spent $X on Y" patterns
            re.compile(r"spent\s+\$?(\d+(?:\.\d{2})?)\s+(?:on|for)\s+(.+)", re.IGNORECASE),
            re.compile(r"paid\s+\$?(\d+(?:\.\d{2})?)\s+(?:for|on)\s+(.+)", re.IGNORECASE),
            
            # "$X for Y" patterns  
            re.compile(r"\$?(\d+(?:\.\d{2})?)\s+(?:for|on)\s+(.+)", re.IGNORECASE),
            
            # "Y $X" patterns
            re.compile(r"(.+?)\s+\$?(\d+(?:\.\d{2})?)$", re.IGNORECASE),
            
            # Simple "$X Y" patterns
            re.compile(r"\$?(\d+(?:\.\d{2})?)\s+(.+)", re.IGNORECASE),
        ]
        return patterns
    
    def _get_category_mapping(self) -> Dict[str, str]:
        """Get keyword-to-category mapping for auto-categorization."""
        return {
            # Food & Dining
            "lunch": "Food & Dining",
            "dinner": "Food & Dining", 
            "breakfast": "Food & Dining",
            "restaurant": "Food & Dining",
            "food": "Food & Dining",
            "groceries": "Food & Dining",
            "grocery": "Food & Dining",
            "coffee": "Food & Dining",
            "cafe": "Food & Dining",
            "pizza": "Food & Dining",
            "mcdonald": "Food & Dining",
            "starbucks": "Food & Dining",
            
            # Transportation
            "gas": "Transportation",
            "fuel": "Transportation",
            "uber": "Transportation",
            "lyft": "Transportation",
            "taxi": "Transportation",
            "bus": "Transportation",
            "train": "Transportation",
            "parking": "Transportation",
            "car": "Transportation",
            
            # Shopping
            "amazon": "Shopping",
            "shopping": "Shopping",
            "clothes": "Shopping",
            "clothing": "Shopping",
            "shoes": "Shopping",
            "electronics": "Shopping",
            "book": "Shopping",
            "books": "Shopping",
            
            # Entertainment
            "movie": "Entertainment",
            "cinema": "Entertainment",
            "theater": "Entertainment",
            "concert": "Entertainment",
            "game": "Entertainment",
            "games": "Entertainment",
            "netflix": "Entertainment",
            "spotify": "Entertainment",
            
            # Bills & Utilities
            "electric": "Bills & Utilities",
            "electricity": "Bills & Utilities",
            "water": "Bills & Utilities",
            "internet": "Bills & Utilities",
            "phone": "Bills & Utilities",
            "rent": "Bills & Utilities",
            "mortgage": "Bills & Utilities",
            "insurance": "Bills & Utilities",
            
            # Healthcare
            "doctor": "Healthcare",
            "hospital": "Healthcare",
            "pharmacy": "Healthcare",
            "medicine": "Healthcare",
            "dental": "Healthcare",
            "medical": "Healthcare",
            
            # Education
            "school": "Education",
            "course": "Education",
            "tuition": "Education",
            "books": "Education",
            "training": "Education",
            
            # Travel
            "hotel": "Travel",
            "flight": "Travel",
            "vacation": "Travel",
            "trip": "Travel",
            "travel": "Travel",
        }
    
    async def extract_expense_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract expense information from natural language text."""
        try:
            text = text.strip()
            
            # Try each pattern to extract amount and description
            for pattern in self.expense_patterns:
                match = pattern.search(text)
                if match:
                    groups = match.groups()
                    
                    # Determine which group is amount vs description
                    if len(groups) == 2:
                        try:
                            amount = float(groups[0])
                            description = groups[1].strip()
                        except ValueError:
                            try:
                                amount = float(groups[1])
                                description = groups[0].strip()
                            except ValueError:
                                continue
                        
                        if amount > 0:
                            # Auto-categorize based on description
                            category = self._categorize_expense(description)
                            
                            return {
                                "amount": amount,
                                "description": description,
                                "category": category,
                                "payment_method": "Unknown",
                                "raw_text": text
                            }
            
            # If no pattern matches, use AI to extract information
            return await self._ai_extract_expense(text)
            
        except Exception as e:
            logger.error(f"Failed to extract expense from text: {e}")
            return None
    
    async def _ai_extract_expense(self, text: str) -> Optional[Dict[str, Any]]:
        """Use AI to extract expense information from complex text."""
        try:
            extraction_prompt = f"""
Extract expense information from this text: "{text}"

Return a JSON object with these fields:
- amount: numeric value (required)
- description: brief description of the expense (required)  
- category: one of {settings.expense_categories} (required)
- payment_method: if mentioned (optional, default "Unknown")

If this doesn't appear to be an expense, return null.

Examples:
"Spent $25 on lunch at Joe's Diner" -> {{"amount": 25, "description": "lunch at Joe's Diner", "category": "Food & Dining", "payment_method": "Unknown"}}
"Gas $45" -> {{"amount": 45, "description": "gas", "category": "Transportation", "payment_method": "Unknown"}}
"""
            
            response = await self.arun(extraction_prompt)
            
            # Parse AI response (simplified - in production would use structured output)
            # This is a placeholder for AI-based extraction
            return None
            
        except Exception as e:
            logger.error(f"AI expense extraction failed: {e}")
            return None
    
    def _categorize_expense(self, description: str) -> str:
        """Automatically categorize expense based on description keywords."""
        description_lower = description.lower()
        
        # Check for keyword matches
        for keyword, category in self.category_mapping.items():
            if keyword in description_lower:
                return category
        
        # Default to "Other" if no match found
        return "Other"
    
    async def log_expense(
        self,
        amount: float,
        description: str,
        category: str,
        payment_method: str = "Unknown",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Log an expense to the Excel spreadsheet."""
        try:
            result = self.excel_manager.add_expense(
                amount=amount,
                category=category,
                description=description,
                payment_method=payment_method,
                notes=notes
            )
            
            if result["success"]:
                # Get budget impact for response
                impact_message = result.get("budget_impact", "")
                
                response_message = f"""
✅ <b>Expense logged successfully!</b>

💰 <b>Amount:</b> ${amount:.2f}
📝 <b>Description:</b> {description}
📊 <b>Category:</b> {category}
💳 <b>Payment:</b> {payment_method}

{impact_message}
"""
                
                # Check if this puts user over budget
                if "exceed budget" in impact_message.lower():
                    response_message += "\n\n⚠️ <b>Budget Alert:</b> This expense puts you over your monthly budget for this category!"
                elif "80%" in impact_message:
                    response_message += "\n\n⚠️ <b>Budget Warning:</b> You're approaching your budget limit for this category."
                
                return {
                    "success": True,
                    "message": response_message,
                    "expense_data": {
                        "amount": amount,
                        "description": description,
                        "category": category,
                        "payment_method": payment_method
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"❌ Failed to log expense: {result.get('error', 'Unknown error')}"
                }
                
        except Exception as e:
            logger.error(f"Failed to log expense: {e}")
            return {
                "success": False,
                "message": f"❌ Error logging expense: {str(e)}"
            }
    
    async def process_expense_message(self, message_text: str) -> str:
        """Process a message and extract/log expense if found."""
        try:
            # Extract expense information
            expense_data = await self.extract_expense_from_text(message_text)
            
            if not expense_data:
                return """
🤔 I couldn't identify an expense in your message. 

Try formats like:
• "Spent $25 on lunch"
• "Gas $45"  
• "Paid $150 for groceries"
• "$28 movie tickets"

Or just tell me what you spent money on!
"""
            
            # Log the expense
            result = await self.log_expense(
                amount=expense_data["amount"],
                description=expense_data["description"],
                category=expense_data["category"],
                payment_method=expense_data["payment_method"]
            )
            
            return result["message"]
            
        except Exception as e:
            logger.error(f"Failed to process expense message: {e}")
            return f"❌ Error processing your expense: {str(e)}"