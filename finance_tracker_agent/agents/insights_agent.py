from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.tools.reasoning import ReasoningTools
from ..tools.excel_tools import ExcelFinanceManager
from ..tools.telegram_tools import TelegramBotTool
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)


class FinancialInsightsAgent(Agent):
    """Agent specialized in generating financial insights and visual reports."""
    
    def __init__(self, excel_manager: ExcelFinanceManager, telegram_tool: Optional[TelegramBotTool] = None):
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
            name="InsightsAnalyst",
            role="Financial Data Analyst and Insights Generator",
            markdown=True,
            show_tool_calls=True
        )
        
        self.excel_manager = excel_manager
        self.telegram_tool = telegram_tool
        self.charts_dir = Path("data/charts")
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
        # Set matplotlib style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def _get_instructions(self) -> str:
        """Get insights agent instructions using GPT-5 best practices."""
        return f"""
<role>
You are a Senior Financial Data Analyst and Insights Specialist who transforms raw financial data into actionable intelligence, compelling visualizations, and strategic recommendations for personal finance optimization.
</role>

<core_expertise>
- **Advanced Analytics**: Statistical analysis, trend detection, pattern recognition
- **Data Visualization**: Chart design, infographic creation, mobile-optimized graphics  
- **Behavioral Finance**: Understanding psychological spending patterns and motivations
- **Strategic Planning**: Long-term financial goal mapping and milestone tracking
- **Performance Optimization**: Identifying efficiency gains and cost reduction opportunities
</core_expertise>

<analytical_framework>
**Data Processing Pipeline:**
1. **Data Ingestion**: Collect and validate financial transaction data
2. **Pattern Recognition**: Identify trends, anomalies, and behavioral patterns
3. **Comparative Analysis**: Benchmark against historical data and user goals
4. **Predictive Modeling**: Forecast future spending and budget performance
5. **Insight Synthesis**: Generate actionable recommendations

**Key Metrics Dashboard:**
- **Spending Velocity**: Daily/weekly burn rates and projections
- **Category Performance**: Budget adherence and variance analysis  
- **Behavioral Indicators**: Transaction frequency, average amounts, timing patterns
- **Financial Health Score**: Composite metric of budgeting discipline
- **Goal Progress**: Savings rates, milestone achievements, target trajectories
</analytical_framework>

<visualization_standards>
**Chart Types and Usage:**
- **Pie Charts**: Category spending breakdowns (max 7 categories + "Other")
- **Bar Charts**: Month-over-month comparisons, budget vs actual
- **Line Charts**: Trend analysis, spending velocity over time
- **Gauge Charts**: Budget utilization percentages  
- **Heatmaps**: Spending patterns by day/time

**Design Principles:**
- **Clarity**: Clean, uncluttered layouts with clear data labels
- **Accessibility**: High contrast colors, readable fonts, mobile-friendly sizing
- **Context**: Always include comparison points and reference lines
- **Hierarchy**: Emphasize key insights through size, color, and positioning
- **Actionability**: Highlight areas requiring user attention or action
</visualization_standards>

<insight_generation>
**Analysis Categories:**

**Spending Behavior Analysis:**
- Identify peak spending days/times and potential triggers  
- Detect unusual transactions that may indicate errors or impulse purchases
- Analyze merchant frequency and loyalty patterns
- Track seasonal spending variations

**Budget Performance Intelligence:**
- Calculate budget adherence scores and trends
- Identify consistently over/under-performing categories
- Predict end-of-month budget status based on current velocity
- Recommend budget adjustments based on actual spending patterns

**Financial Health Indicators:**
- Savings rate calculation and trend analysis
- Emergency fund adequacy assessment  
- Debt-to-spending ratios and improvement tracking
- Goal progress and timeline feasibility analysis
</insight_generation>

<reporting_templates>
**Monthly Financial Report Structure:**
```
📊 **Financial Health Report - [Month Year]**

🎯 **Executive Summary**
• Overall Performance: [Score/10]
• Budget Adherence: [Percentage]
• Savings Rate: [Percentage]
• Key Achievement: [Highlight]

📈 **Spending Analysis**  
• Total Spent: $[amount] ([+/-]% vs last month)
• Top Category: [Category] ($[amount])
• Biggest Change: [Category] ([+/-]% change)

💡 **Key Insights**
• [3-5 bullet points with specific, actionable insights]

🎯 **Recommendations**
• [Numbered list of specific actions to take]

📊 **Visual Data**
[Chart descriptions and key findings]
```

**Alert Templates:**
- **Positive**: "🎉 Great job staying under budget in [category]!"
- **Warning**: "⚠️ You're at [%] of your [category] budget with [days] remaining"  
- **Critical**: "🚨 Budget exceeded in [category]. Here's what to do..."
</reporting_templates>

<communication_guidelines>
**Tone and Style:**
- **Data-Driven**: Base all insights on concrete numbers and trends
- **Encouraging**: Frame setbacks as learning opportunities
- **Actionable**: Every insight should include specific next steps
- **Accessible**: Explain complex concepts in simple terms
- **Motivational**: Celebrate progress and achievements

**Formatting Standards:**
- Use **bold** for key metrics and important numbers
- Include 📊 📈 📉 💰 🎯 for visual categorization
- Structure complex information with numbered lists
- Highlight critical information with appropriate emoji alerts
- Maintain consistent currency formatting ($1,234.56)
</communication_guidelines>

<advanced_features>
**Predictive Analytics:**
- Forecast end-of-month spending based on current trends
- Predict budget overrun probability and suggest interventions
- Model seasonal spending adjustments needed

**Comparative Intelligence:**
- Benchmark spending against national/demographic averages
- Compare current performance to user's historical patterns
- Identify improvement trends and celebrate progress

**Goal Integration:**
- Track progress toward savings and debt reduction goals
- Calculate required spending adjustments to meet targets
- Provide milestone celebrations and motivation
</advanced_features>

<reasoning_effort>
Use high reasoning effort to:
- Perform complex statistical analysis of spending patterns
- Generate sophisticated insights from multi-dimensional data
- Create compelling narratives from numerical data
- Develop personalized, context-aware recommendations
</reasoning_effort>
"""
    
    async def generate_monthly_report(self, month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """Generate comprehensive monthly financial report."""
        try:
            if month is None:
                month = datetime.now().month
            if year is None:
                year = datetime.now().year
            
            # Get spending data
            current_summary = self.excel_manager.get_spending_summary(month, year)
            
            if not current_summary["success"]:
                return {
                    "success": False,
                    "message": "❌ Unable to generate report - no data available"
                }
            
            # Get previous month for comparison
            prev_date = datetime(year, month, 1) - timedelta(days=1)
            prev_summary = self.excel_manager.get_spending_summary(prev_date.month, prev_date.year)
            
            # Generate visualizations
            chart_paths = await self._create_monthly_charts(current_summary, prev_summary, month, year)
            
            # Generate insights
            insights = await self._analyze_monthly_patterns(current_summary, prev_summary)
            
            # Create text summary
            report_text = self._format_monthly_report(current_summary, prev_summary, insights, month, year)
            
            return {
                "success": True,
                "report_text": report_text,
                "chart_paths": chart_paths,
                "insights": insights
            }
            
        except Exception as e:
            logger.error(f"Failed to generate monthly report: {e}")
            return {
                "success": False,
                "message": f"❌ Error generating report: {str(e)}"
            }
    
    async def _create_monthly_charts(
        self, 
        current_summary: Dict[str, Any], 
        prev_summary: Dict[str, Any],
        month: int, 
        year: int
    ) -> List[Path]:
        """Create visual charts for monthly report."""
        chart_paths = []
        
        try:
            # Chart 1: Category Breakdown Pie Chart
            if current_summary["category_breakdown"]:
                pie_path = await self._create_category_pie_chart(
                    current_summary["category_breakdown"], month, year
                )
                if pie_path:
                    chart_paths.append(pie_path)
            
            # Chart 2: Month-over-Month Comparison
            if prev_summary["success"]:
                comparison_path = await self._create_comparison_chart(
                    current_summary, prev_summary, month, year
                )
                if comparison_path:
                    chart_paths.append(comparison_path)
            
            # Chart 3: Daily Spending Trend (if we have detailed data)
            trend_path = await self._create_spending_trend_chart(month, year)
            if trend_path:
                chart_paths.append(trend_path)
            
        except Exception as e:
            logger.error(f"Failed to create charts: {e}")
        
        return chart_paths
    
    async def _create_category_pie_chart(self, category_data: Dict[str, float], month: int, year: int) -> Optional[Path]:
        """Create pie chart showing spending by category."""
        try:
            # Sort categories by amount
            sorted_categories = sorted(category_data.items(), key=lambda x: x[1], reverse=True)
            
            # Take top 7 categories, group rest as "Other"
            if len(sorted_categories) > 7:
                top_categories = sorted_categories[:7]
                other_amount = sum(amount for _, amount in sorted_categories[7:])
                if other_amount > 0:
                    top_categories.append(("Other", other_amount))
            else:
                top_categories = sorted_categories
            
            categories, amounts = zip(*top_categories) if top_categories else ([], [])
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Create pie chart with better colors
            colors = plt.cm.Set3(range(len(categories)))
            wedges, texts, autotexts = ax.pie(
                amounts, 
                labels=categories,
                autopct='%1.1f%%',
                startangle=90,
                colors=colors,
                textprops={'fontsize': 10}
            )
            
            # Enhance appearance
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title(
                f'Spending by Category - {datetime(year, month, 1).strftime("%B %Y")}',
                fontsize=14,
                fontweight='bold',
                pad=20
            )
            
            # Add total spending annotation
            total = sum(amounts)
            fig.text(0.5, 0.02, f'Total Spending: ${total:.2f}', ha='center', fontsize=12, style='italic')
            
            plt.tight_layout()
            
            # Save chart
            chart_path = self.charts_dir / f"category_breakdown_{year}_{month:02d}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Failed to create pie chart: {e}")
            return None
    
    async def _create_comparison_chart(
        self, 
        current_summary: Dict[str, Any], 
        prev_summary: Dict[str, Any],
        month: int, 
        year: int
    ) -> Optional[Path]:
        """Create bar chart comparing current vs previous month."""
        try:
            current_breakdown = current_summary["category_breakdown"]
            prev_breakdown = prev_summary.get("category_breakdown", {})
            
            # Get all categories
            all_categories = set(current_breakdown.keys()) | set(prev_breakdown.keys())
            
            categories = []
            current_amounts = []
            prev_amounts = []
            
            for category in sorted(all_categories):
                categories.append(category)
                current_amounts.append(current_breakdown.get(category, 0))
                prev_amounts.append(prev_breakdown.get(category, 0))
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 8))
            
            x = range(len(categories))
            width = 0.35
            
            # Create bars
            bars1 = ax.bar([i - width/2 for i in x], prev_amounts, width, 
                          label=f'Previous Month', color='lightblue', alpha=0.7)
            bars2 = ax.bar([i + width/2 for i in x], current_amounts, width,
                          label=f'Current Month', color='darkblue', alpha=0.8)
            
            # Add value labels on bars
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    if height > 0:
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'${height:.0f}', ha='center', va='bottom', fontsize=9)
            
            # Customize chart
            ax.set_xlabel('Categories', fontweight='bold')
            ax.set_ylabel('Amount Spent ($)', fontweight='bold')
            ax.set_title(f'Spending Comparison - {datetime(year, month, 1).strftime("%B %Y")}', 
                        fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(categories, rotation=45, ha='right')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            
            # Save chart
            chart_path = self.charts_dir / f"comparison_{year}_{month:02d}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Failed to create comparison chart: {e}")
            return None
    
    async def _create_spending_trend_chart(self, month: int, year: int) -> Optional[Path]:
        """Create line chart showing daily spending trend."""
        try:
            # This would require accessing raw expense data
            # For now, create a placeholder chart showing weekly spending
            
            # Get expense data from Excel
            expenses_df = pd.read_excel(settings.excel_file_path, sheet_name="Expenses")
            expenses_df['Date'] = pd.to_datetime(expenses_df['Date'])
            
            # Filter for current month
            month_data = expenses_df[
                (expenses_df['Date'].dt.month == month) & 
                (expenses_df['Date'].dt.year == year)
            ]
            
            if month_data.empty:
                return None
            
            # Group by day
            daily_spending = month_data.groupby(month_data['Date'].dt.date)['Amount'].sum().reset_index()
            daily_spending['Date'] = pd.to_datetime(daily_spending['Date'])
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Plot line
            ax.plot(daily_spending['Date'], daily_spending['Amount'], 
                   marker='o', linewidth=2, markersize=4, color='green')
            
            # Add trend line
            z = np.polyfit(range(len(daily_spending)), daily_spending['Amount'], 1)
            p = np.poly1d(z)
            ax.plot(daily_spending['Date'], p(range(len(daily_spending))), 
                   "--", alpha=0.7, color='red', label='Trend')
            
            # Customize chart
            ax.set_xlabel('Date', fontweight='bold')
            ax.set_ylabel('Daily Spending ($)', fontweight='bold')
            ax.set_title(f'Daily Spending Trend - {datetime(year, month, 1).strftime("%B %Y")}', 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format x-axis
            fig.autofmt_xdate()
            
            plt.tight_layout()
            
            # Save chart
            chart_path = self.charts_dir / f"trend_{year}_{month:02d}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Failed to create trend chart: {e}")
            return None
    
    async def _analyze_monthly_patterns(
        self, 
        current_summary: Dict[str, Any], 
        prev_summary: Dict[str, Any]
    ) -> List[str]:
        """Analyze spending patterns and generate insights."""
        insights = []
        
        try:
            current_total = current_summary["total_spent"]
            current_breakdown = current_summary["category_breakdown"]
            current_count = current_summary["transaction_count"]
            current_avg = current_summary["average_transaction"]
            
            # Compare with previous month if available
            if prev_summary["success"]:
                prev_total = prev_summary["total_spent"]
                prev_breakdown = prev_summary.get("category_breakdown", {})
                
                # Total spending change
                if prev_total > 0:
                    change_pct = ((current_total - prev_total) / prev_total) * 100
                    if change_pct > 10:
                        insights.append(f"📈 Spending increased by {change_pct:.1f}% from last month (${current_total - prev_total:.2f} more)")
                    elif change_pct < -10:
                        insights.append(f"📉 Great job! Spending decreased by {abs(change_pct):.1f}% from last month (${abs(current_total - prev_total):.2f} saved)")
                    else:
                        insights.append(f"📊 Spending remained stable (only {abs(change_pct):.1f}% change from last month)")
                
                # Category-wise analysis
                for category, current_amount in current_breakdown.items():
                    prev_amount = prev_breakdown.get(category, 0)
                    if prev_amount > 0:
                        cat_change_pct = ((current_amount - prev_amount) / prev_amount) * 100
                        if cat_change_pct > 25:
                            insights.append(f"⚠️ {category} spending spiked by {cat_change_pct:.1f}% - worth reviewing")
                        elif cat_change_pct < -25:
                            insights.append(f"✅ {category} spending reduced by {abs(cat_change_pct):.1f}% - excellent control!")
            
            # Transaction patterns
            if current_count > 0:
                if current_avg > 100:
                    insights.append(f"💳 High average transaction amount (${current_avg:.2f}) - mostly larger purchases")
                elif current_avg < 20:
                    insights.append(f"🛒 Many small transactions (avg ${current_avg:.2f}) - frequent small purchases")
                
                if current_count > 60:  # More than 2 per day
                    insights.append(f"📱 High transaction frequency ({current_count} transactions) - consider consolidating purchases")
            
            # Top category insights
            if current_breakdown:
                top_category = max(current_breakdown, key=current_breakdown.get)
                top_amount = current_breakdown[top_category]
                top_pct = (top_amount / current_total) * 100
                
                insights.append(f"🏆 Top spending category: {top_category} (${top_amount:.2f}, {top_pct:.1f}% of total)")
                
                if top_pct > 50:
                    insights.append(f"⚠️ {top_category} dominates your spending ({top_pct:.1f}%) - consider diversifying")
            
            # Budget adherence insights would go here (requires budget data)
            
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}")
            insights.append("❌ Unable to generate detailed insights due to data analysis error")
        
        return insights
    
    def _format_monthly_report(
        self, 
        current_summary: Dict[str, Any], 
        prev_summary: Dict[str, Any],
        insights: List[str],
        month: int, 
        year: int
    ) -> str:
        """Format monthly report text."""
        month_name = datetime(year, month, 1).strftime("%B %Y")
        
        report = f"""
📊 <b>Monthly Financial Report - {month_name}</b>

💰 <b>Summary</b>
• Total Spent: ${current_summary['total_spent']:.2f}
• Transactions: {current_summary['transaction_count']}
• Average per Transaction: ${current_summary['average_transaction']:.2f}

🏆 <b>Top Categories</b>
"""
        
        # Add top 5 categories
        sorted_categories = sorted(
            current_summary['category_breakdown'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for i, (category, amount) in enumerate(sorted_categories[:5], 1):
            percentage = (amount / current_summary['total_spent']) * 100
            report += f"{i}. {category}: ${amount:.2f} ({percentage:.1f}%)\n"
        
        # Add insights
        if insights:
            report += "\n💡 <b>Key Insights</b>\n"
            for insight in insights[:5]:  # Limit to top 5 insights
                report += f"• {insight}\n"
        
        # Add comparison if available
        if prev_summary["success"]:
            prev_total = prev_summary["total_spent"]
            change = current_summary["total_spent"] - prev_total
            change_pct = (change / prev_total * 100) if prev_total > 0 else 0
            
            report += f"\n📈 <b>vs. Previous Month</b>\n"
            if change >= 0:
                report += f"• Spent ${change:.2f} more (+{change_pct:.1f}%)\n"
            else:
                report += f"• Spent ${abs(change):.2f} less ({change_pct:.1f}%)\n"
        
        return report
    
    async def send_monthly_report(self, chat_id: Optional[str] = None) -> str:
        """Generate and send monthly report via Telegram."""
        try:
            if not self.telegram_tool:
                return "❌ Telegram integration not configured"
            
            # Generate report
            report_data = await self.generate_monthly_report()
            
            if not report_data["success"]:
                return report_data["message"]
            
            # Send text report
            await self.telegram_tool.send_message(
                message=report_data["report_text"],
                chat_id=chat_id
            )
            
            # Send charts
            for chart_path in report_data["chart_paths"]:
                if chart_path.exists():
                    await self.telegram_tool.send_photo(
                        photo_path=chart_path,
                        caption=f"Financial Chart - {chart_path.stem}",
                        chat_id=chat_id
                    )
            
            return "✅ Monthly report sent successfully!"
            
        except Exception as e:
            logger.error(f"Failed to send monthly report: {e}")
            return f"❌ Error sending report: {str(e)}"