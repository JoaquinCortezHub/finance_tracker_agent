from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.tools.reasoning import ReasoningTools
from ..tools.excel_tools import ExcelFinanceManager
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)


class BudgetMonitoringAgent(Agent):
    """Agent specialized in budget monitoring and financial goal tracking."""
    
    def __init__(self, excel_manager: ExcelFinanceManager):
        # Choose model based on available API keys
        if settings.anthropic_api_key:
            model = Claude(id="claude-sonnet-4-20250514", api_key=settings.anthropic_api_key)
        elif settings.openai_api_key:
            model = OpenAIChat(id="gpt-5", api_key=settings.openai_api_key)
        else:
            raise ValueError("No API key provided for AI model")
        
        super().__init__(
            model=model,
            tools=[ReasoningTools(add_instructions=True)],
            instructions=self._get_instructions(),
            name="BudgetMonitor",
            role="Financial Budget and Goals Assistant",
            markdown=True,
            show_tool_calls=True
        )
        
        self.excel_manager = excel_manager
        self.alert_thresholds = {
            "warning": 0.8,  # 80% of budget used
            "critical": 1.0,  # 100% of budget used
            "severe": 1.2   # 120% of budget used (over budget)
        }
    
    def _get_instructions(self) -> str:
        """Get budget agent instructions using GPT-5 best practices."""
        return f"""
<role>
You are a Strategic Budget Management Specialist focused on helping users create, monitor, and optimize their personal budgets with intelligent guidance and real-time insights.
</role>

<core_responsibilities>
- **Budget Architecture**: Design realistic, sustainable budget frameworks
- **Real-Time Monitoring**: Track spending against budget limits with intelligent alerts
- **Behavioral Analysis**: Identify spending patterns and suggest optimizations
- **Proactive Guidance**: Prevent overspending through early warnings and alternatives
- **Financial Coaching**: Educate users on effective budget management strategies
</core_responsibilities>

<budget_management_framework>
**Budget Creation Process:**
1. **Assessment**: Analyze user's income, fixed expenses, and financial goals
2. **Categorization**: Allocate appropriate amounts to each expense category
3. **Validation**: Ensure budgets are realistic and sustainable
4. **Implementation**: Set up tracking and monitoring systems

**Budget Categories:**
{', '.join(settings.expense_categories)}

**Budget Adjustment Logic:**
- Recommend 50/30/20 rule as baseline (needs/wants/savings)
- Adjust based on user's actual spending patterns
- Consider seasonal variations and life changes
- Maintain emergency buffer in allocations
</budget_management_framework>

<monitoring_system>
**Alert Thresholds:**
- 🟢 **Healthy** (0-65%): Encourage continued good habits
- 🟡 **Caution** (66-80%): Provide gentle reminders and tips
- 🟠 **Warning** (81-95%): Suggest specific actions to avoid overspend
- 🔴 **Critical** (96-100%): Immediate intervention recommendations
- ⚡ **Over Budget** (100%+): Crisis management and recovery plans

**Monitoring Intelligence:**
- Track velocity of spending (daily/weekly rates)
- Compare current month to historical averages
- Identify unusual spending spikes requiring attention
- Predict end-of-month budget status based on current trends
</monitoring_system>

<communication_protocols>
**Budget Status Updates:**
```
📊 **Budget Status - [Category]**
• Allocated: $[budget] for [month]
• Spent: $[spent] ([percentage]%)
• Remaining: $[remaining] ([days] days left)
• Status: [status_indicator]
```

**Guidance Tone:**
- **Encouraging**: Celebrate good budget adherence
- **Constructive**: Frame overspending as learning opportunities
- **Actionable**: Always provide specific next steps
- **Empowering**: Help users feel in control of their finances

**Response Formats:**
- Use **bold** for key information and amounts
- Include 📊 📈 📉 for data visualization
- Add ✅ ⚠️ 🚨 for status indicators
- Provide numbered action items for complex guidance
</communication_protocols>

<command_interpretation>
**Budget Setting Commands:**
- "Set food budget to $400" → Update Food & Dining category
- "Increase entertainment by $50" → Add $50 to current Entertainment budget
- "Budget $200 for transportation" → Set Transportation category budget

**Status Check Commands:**
- "Check budget status" → Comprehensive overview all categories
- "How much left for shopping?" → Specific category remaining balance
- "Am I over budget?" → Over-budget categories and amounts

**Analysis Commands:**
- "Budget performance this month" → Detailed analysis with trends
- "Which categories need adjustment?" → Optimization recommendations
</command_interpretation>

<intelligent_recommendations>
**Budget Optimization:**
- Identify consistently under/over-spent categories
- Suggest realistic adjustments based on 3-month trends
- Recommend seasonal budget variations
- Propose cost-saving strategies for over-budget categories

**Spending Alternatives:**
- Suggest lower-cost alternatives when approaching limits
- Recommend category shifts for flexible expenses
- Provide timing suggestions (e.g., "Wait until next month for this purchase")

**Financial Health Indicators:**
- Track budget adherence score (percentage on-budget categories)
- Monitor month-over-month improvement trends
- Calculate savings rate and emergency fund progress
</intelligent_recommendations>

<crisis_management>
**Over-Budget Response Protocol:**
1. **Immediate Assessment**: Calculate overage amount and impact
2. **Root Cause Analysis**: Identify why budget was exceeded
3. **Damage Control**: Suggest immediate cost-cutting measures
4. **Recovery Plan**: Provide realistic path back to budget compliance
5. **Prevention**: Recommend safeguards to prevent recurrence

**Emergency Scenarios:**
- Unexpected large expenses
- Income reduction situations  
- Multiple categories over budget
- Chronic budget non-adherence
</crisis_management>

<reasoning_effort>
Use medium reasoning effort to:
- Analyze spending patterns and trends
- Calculate realistic budget recommendations
- Provide personalized financial guidance
- Anticipate user needs and concerns
</reasoning_effort>
"""
    
    async def set_category_budget(self, category: str, amount: float) -> str:
        """Set budget for a specific category."""
        try:
            if category not in settings.expense_categories:
                return f"""
❌ <b>Invalid Category</b>

"{category}" is not a recognized category. Please choose from:
{', '.join(settings.expense_categories)}
"""
            
            if amount <= 0:
                return "❌ Budget amount must be positive. Please try again with a valid amount."
            
            result = self.excel_manager.set_budget(category, amount)
            
            if result["success"]:
                # Get current spending for this category to provide immediate feedback
                current_month = datetime.now().month
                current_year = datetime.now().year
                summary = self.excel_manager.get_spending_summary(current_month, current_year)
                
                current_spent = 0
                if summary["success"] and category in summary["category_breakdown"]:
                    current_spent = summary["category_breakdown"][category]
                
                response = f"""
✅ <b>Budget Set Successfully!</b>

📊 <b>Category:</b> {category}
💰 <b>Monthly Budget:</b> ${amount:.2f}
💸 <b>Current Spent:</b> ${current_spent:.2f}
💵 <b>Remaining:</b> ${amount - current_spent:.2f}
"""
                
                # Add status-based advice
                if current_spent > amount:
                    response += f"\n⚠️ <b>Over Budget:</b> You've already exceeded this budget by ${current_spent - amount:.2f} this month."
                elif current_spent / amount > 0.8:
                    percentage = (current_spent / amount) * 100
                    response += f"\n⚠️ <b>Budget Warning:</b> You've used {percentage:.1f}% of this budget."
                else:
                    percentage = (current_spent / amount) * 100
                    response += f"\n✅ <b>On Track:</b> You've used {percentage:.1f}% of this budget."
                
                return response
            else:
                return f"❌ Failed to set budget: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Failed to set budget: {e}")
            return f"❌ Error setting budget: {str(e)}"
    
    async def get_budget_status(self) -> str:
        """Get current budget status for all categories."""
        try:
            budget_data = self.excel_manager.get_budget_status()
            
            if not budget_data["success"]:
                return f"❌ Failed to get budget status: {budget_data.get('error', 'Unknown error')}"
            
            if not budget_data["budget_status"]:
                return """
📊 <b>Budget Status</b>

No budgets have been set yet. Use the format:
"Set budget for [category] $[amount]"

Example: "Set budget for Food & Dining $500"
"""
            
            response = "📊 <b>Current Budget Status</b>\n\n"
            
            total_budget = 0
            total_spent = 0
            alerts = []
            
            for budget in budget_data["budget_status"]:
                category = budget["category"]
                monthly_budget = budget["budget"] or 0
                spent = budget["spent"] or 0
                remaining = budget["remaining"] or 0
                status = budget["status"]
                
                total_budget += monthly_budget
                total_spent += spent
                
                # Status emoji
                if status == "OVER BUDGET":
                    emoji = "🔴"
                    alerts.append(f"• {category}: Over budget by ${abs(remaining):.2f}")
                elif status == "WARNING":
                    emoji = "🟡"
                    alerts.append(f"• {category}: Approaching limit (${remaining:.2f} left)")
                elif status == "OK":
                    emoji = "🟢"
                else:
                    emoji = "⚪"
                
                if monthly_budget > 0:
                    percentage = (spent / monthly_budget) * 100
                    response += f"{emoji} <b>{category}</b>\n"
                    response += f"   Budget: ${monthly_budget:.2f} | Spent: ${spent:.2f} ({percentage:.1f}%)\n"
                    response += f"   Remaining: ${remaining:.2f}\n\n"
            
            # Overall summary
            if total_budget > 0:
                overall_percentage = (total_spent / total_budget) * 100
                response += f"💰 <b>Overall Budget Performance</b>\n"
                response += f"Total Budget: ${total_budget:.2f}\n"
                response += f"Total Spent: ${total_spent:.2f} ({overall_percentage:.1f}%)\n"
                response += f"Total Remaining: ${total_budget - total_spent:.2f}\n\n"
            
            # Alerts section
            if alerts:
                response += "⚠️ <b>Budget Alerts</b>\n"
                for alert in alerts:
                    response += f"{alert}\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get budget status: {e}")
            return f"❌ Error getting budget status: {str(e)}"
    
    async def check_budget_alerts(self, category: str, new_expense_amount: float) -> List[str]:
        """Check for budget alerts when a new expense is added."""
        try:
            budget_data = self.excel_manager.get_budget_status()
            
            if not budget_data["success"]:
                return []
            
            alerts = []
            
            for budget in budget_data["budget_status"]:
                if budget["category"] == category:
                    monthly_budget = budget["budget"] or 0
                    current_spent = budget["spent"] or 0
                    
                    if monthly_budget <= 0:
                        continue
                    
                    new_total = current_spent + new_expense_amount
                    new_percentage = (new_total / monthly_budget) * 100
                    
                    if new_percentage >= self.alert_thresholds["severe"] * 100:
                        alerts.append(f"🚨 CRITICAL: {category} budget exceeded by ${new_total - monthly_budget:.2f}!")
                    elif new_percentage >= self.alert_thresholds["critical"] * 100:
                        alerts.append(f"🔴 ALERT: {category} budget limit reached!")
                    elif new_percentage >= self.alert_thresholds["warning"] * 100:
                        alerts.append(f"🟡 WARNING: {category} approaching budget limit ({new_percentage:.1f}% used)")
                    
                    break
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to check budget alerts: {e}")
            return []
    
    async def suggest_budget_adjustments(self) -> str:
        """Analyze spending patterns and suggest budget adjustments."""
        try:
            # Get current month and previous month data
            now = datetime.now()
            current_summary = self.excel_manager.get_spending_summary(now.month, now.year)
            
            # Get previous month
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            prev_summary = self.excel_manager.get_spending_summary(
                prev_month_date.month, prev_month_date.year
            )
            
            if not current_summary["success"]:
                return "❌ Unable to analyze spending patterns at this time."
            
            response = "💡 <b>Budget Optimization Suggestions</b>\n\n"
            
            current_breakdown = current_summary["category_breakdown"]
            prev_breakdown = prev_summary.get("category_breakdown", {}) if prev_summary["success"] else {}
            
            suggestions = []
            
            # Analyze each category
            for category, current_spent in current_breakdown.items():
                prev_spent = prev_breakdown.get(category, 0)
                
                # Get current budget for this category
                budget_data = self.excel_manager.get_budget_status()
                category_budget = 0
                
                if budget_data["success"]:
                    for budget in budget_data["budget_status"]:
                        if budget["category"] == category:
                            category_budget = budget["budget"] or 0
                            break
                
                # Analyze spending pattern
                if category_budget > 0:
                    usage_percentage = (current_spent / category_budget) * 100
                    
                    if usage_percentage > 120:
                        suggestions.append(f"🔴 {category}: Consider increasing budget from ${category_budget:.2f} to ${current_spent * 1.1:.2f}")
                    elif usage_percentage < 50 and current_spent > 0:
                        suggestions.append(f"🟢 {category}: Budget may be too high. Consider reducing from ${category_budget:.2f} to ${current_spent * 2:.2f}")
                
                # Compare with previous month
                if prev_spent > 0:
                    change_percentage = ((current_spent - prev_spent) / prev_spent) * 100
                    if abs(change_percentage) > 50:
                        if change_percentage > 0:
                            suggestions.append(f"📈 {category}: Spending increased by {change_percentage:.1f}% from last month")
                        else:
                            suggestions.append(f"📉 {category}: Great job! Spending decreased by {abs(change_percentage):.1f}% from last month")
                
                # Suggest budget for categories without one
                elif category_budget == 0 and current_spent > 0:
                    suggested_budget = current_spent * 1.2  # 20% buffer
                    suggestions.append(f"💡 {category}: No budget set. Consider ${suggested_budget:.2f} based on current spending")
            
            if suggestions:
                for suggestion in suggestions[:5]:  # Limit to top 5 suggestions
                    response += f"{suggestion}\n"
            else:
                response += "✅ Your budget allocation looks well-balanced based on current spending patterns!"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate budget suggestions: {e}")
            return f"❌ Error analyzing budget: {str(e)}"
    
    async def process_budget_command(self, command_text: str) -> str:
        """Process budget-related commands."""
        try:
            command_lower = command_text.lower().strip()
            
            # Set budget command
            if command_lower.startswith("set budget"):
                # Parse "set budget for [category] $[amount]"
                parts = command_text.split()
                if len(parts) >= 5 and "for" in command_lower:
                    try:
                        for_idx = [i for i, word in enumerate(parts) if word.lower() == "for"][0]
                        amount_part = parts[-1].replace("$", "")
                        amount = float(amount_part)
                        category = " ".join(parts[for_idx + 1:-1])
                        
                        return await self.set_category_budget(category, amount)
                    except (ValueError, IndexError):
                        pass
                
                return """
❌ <b>Invalid budget command format</b>

Use: "Set budget for [category] $[amount]"

Examples:
• "Set budget for Food & Dining $500"
• "Set budget for Transportation $200"
• "Set budget for Entertainment $150"
"""
            
            # Budget status/overview commands
            elif any(word in command_lower for word in ["status", "overview", "check", "show"]):
                return await self.get_budget_status()
            
            # Budget suggestions
            elif any(word in command_lower for word in ["suggest", "advice", "optimize", "improve"]):
                return await self.suggest_budget_adjustments()
            
            # Default budget help
            else:
                return """
📊 <b>Budget Commands Help</b>

Available commands:
• <code>/budget status</code> - Show current budget status
• <code>Set budget for [category] $[amount]</code> - Set category budget
• <code>/budget suggest</code> - Get budget optimization suggestions

Categories: {', '.join(settings.expense_categories)}

Examples:
• "Set budget for Food & Dining $500"
• "/budget status" 
• "/budget suggest"
"""
            
        except Exception as e:
            logger.error(f"Failed to process budget command: {e}")
            return f"❌ Error processing budget command: {str(e)}"