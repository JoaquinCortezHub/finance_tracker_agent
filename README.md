# Finance Tracker Agent

A sophisticated multi-agent system for personal finance management using the Agno framework. Track expenses through Telegram, maintain budgets, and receive intelligent financial insights - all powered by AI agents that automatically categorize and analyze your spending patterns.

## Features

### Smart Expense Tracking
- **Natural Language Processing**: Simply type "Spent $25 on lunch" in Telegram
- **Automatic Categorization**: AI-powered expense categorization into predefined categories
- **Excel Integration**: All data automatically saved to Excel spreadsheets
- **Payment Method Tracking**: Track cash, card, and digital payments

### Budget Management
- **Category-Based Budgets**: Set monthly budgets for different spending categories
- **Real-time Monitoring**: Instant alerts when approaching or exceeding budget limits
- **Smart Suggestions**: AI-powered budget optimization recommendations
- **Progress Tracking**: Visual progress indicators and percentage usage

### Financial Insights & Reports
- **Monthly Reports**: Comprehensive financial analysis with charts and trends
- **Visual Analytics**: Pie charts, bar graphs, and trend analysis
- **Spending Patterns**: Identify unusual spending behaviors and trends
- **Comparative Analysis**: Month-over-month spending comparisons

### Multi-Agent Architecture
- **Expense Agent**: Handles expense extraction and logging
- **Budget Agent**: Manages budgets and alerts
- **Insights Agent**: Generates reports and visual analytics
- **Telegram Integration**: Seamless chat interface

## Quick Start

### Prerequisites
- Python 3.13+
- Telegram Bot Token ([Get one from @BotFather](https://t.me/BotFather))
- OpenAI or Anthropic API Key
- uv package manager (recommended) or pip

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd finance_tracker_agent
   ```

2. **Install Dependencies**
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

3. **Configure Environment**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

4. **Required Environment Variables**
   ```env
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
   TELEGRAM_CHAT_ID=your_telegram_chat_id

   # AI Model API Key (choose one)
   ANTHROPIC_API_KEY=your_anthropic_key
   # OR
   OPENAI_API_KEY=your_openai_key

   # Optional: Customize paths and settings
   EXCEL_FILE_PATH=data/finance_tracker.xlsx
   DEFAULT_CURRENCY=USD
   ```

5. **Run the Application**
   ```bash
   python main.py
   ```

## Usage

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and setup | `/start` |
| `/help` | Show all available commands | `/help` |
| `/balance` | Current month spending summary | `/balance` |
| `/budget` | Budget management | `/budget status` |
| `/report` | Generate monthly report | `/report` |

### Expense Logging

Just type your expenses naturally in the Telegram chat:

```
Simple formats:
"Spent $25 on lunch"
"Gas $45"
"Paid $150 for groceries"
"$28 movie tickets"
"Coffee $5.50"

The AI will automatically:
- Extract the amount and description
- Categorize the expense
- Check against your budgets
- Log to Excel spreadsheet
```

### Budget Management

```
Set budgets:
"Set budget for Food & Dining $500"
"Set budget for Transportation $200"

Check status:
"/budget status"
"/budget suggest"
```

### Available Categories

- Food & Dining
- Transportation  
- Shopping
- Entertainment
- Bills & Utilities
- Healthcare
- Education
- Travel
- Savings & Investment
- Other

## Excel Structure

The system creates an Excel file with multiple sheets:

### Sheets Overview
- **Expenses**: All individual transactions with categories and dates
- **Budget**: Category budgets and spending tracking
- **Monthly Summary**: High-level monthly financial summaries
- **Goals**: Financial goals and progress tracking (future feature)

### Sample Data Structure

**Expenses Sheet:**
| Date | Amount | Category | Description | Payment Method | Notes |
|------|---------|----------|-------------|----------------|-------|
| 2024-01-15 | 25.00 | Food & Dining | lunch at Joe's | Credit Card | - |
| 2024-01-15 | 45.00 | Transportation | gas | Debit Card | Shell station |

**Budget Sheet:**
| Category | Monthly Budget | Current Spent | Remaining | Percentage Used | Status |
|----------|----------------|---------------|-----------|-----------------|---------|
| Food & Dining | 500.00 | 342.50 | 157.50 | 68.5% | OK |
| Transportation | 200.00 | 180.00 | 20.00 | 90.0% | WARNING |

## Architecture

### Agno Framework Integration
Built using the [Agno framework](https://agno.com) for robust multi-agent orchestration:

```
Project Structure:
├── finance_tracker_agent/
│   ├── agents/           # AI agents for different tasks
│   │   ├── expense_agent.py      # Expense tracking & categorization
│   │   ├── budget_agent.py       # Budget monitoring & alerts
│   │   └── insights_agent.py     # Analytics & reporting
│   ├── tools/            # Integration tools
│   │   ├── telegram_tools.py     # Telegram Bot API
│   │   └── excel_tools.py        # Excel operations
│   ├── workflows/        # Agent orchestration
│   │   └── finance_workflow.py   # Main workflow controller
│   ├── config/          # Configuration management
│   │   └── settings.py           # Settings and validation
│   ├── models/          # Data models (future)
│   └── storage/         # Data storage utilities (future)
├── main.py              # Application entry point
├── pyproject.toml       # Dependencies and metadata
└── .env.template        # Environment configuration template
```

### Agent Responsibilities

1. **ExpenseTrackingAgent**: 
   - Natural language expense extraction
   - Automatic categorization using keywords and AI
   - Excel logging with budget impact analysis

2. **BudgetMonitoringAgent**:
   - Budget setting and management
   - Real-time spending alerts
   - Budget optimization suggestions

3. **FinancialInsightsAgent**:
   - Monthly report generation
   - Visual chart creation (matplotlib/plotly)
   - Trend analysis and financial insights

## Development

### Running Tests
```bash
# Install dev dependencies
uv sync --dev

# Run tests
pytest

# Type checking
mypy finance_tracker_agent/

# Code formatting
black finance_tracker_agent/
ruff finance_tracker_agent/
```

### Adding New Features

1. **New Agent**: Create in `agents/` directory, extend `agno.agent.Agent`
2. **New Tool**: Create in `tools/` directory, extend `agno.tools.base.Tool`  
3. **Integration**: Update `workflows/finance_workflow.py` to orchestrate new components

### Configuration

Customize behavior through environment variables:

```env
# Application Settings
DEBUG=true
LOG_LEVEL=DEBUG

# Financial Settings
DEFAULT_CURRENCY=EUR
EXCEL_FILE_PATH=custom/path/finances.xlsx

# Database (for future agent memory)
DATABASE_URL=postgresql://user:pass@localhost/financedb
```

## Privacy & Security

- **Local Data Storage**: All financial data stored locally in Excel files
- **No Data Collection**: No personal financial data sent to external services
- **API Key Security**: Environment-based configuration for API keys
- **Telegram Security**: Bot token and chat ID validation

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

### Common Issues

**Bot not responding:**
- Check TELEGRAM_BOT_TOKEN is correct
- Verify bot is started with `/start` command
- Check logs in `finance_tracker.log`

**Excel file not updating:**
- Ensure write permissions to data directory
- Check EXCEL_FILE_PATH in .env file
- Verify openpyxl installation

**AI categorization not working:**
- Verify API key (ANTHROPIC_API_KEY or OPENAI_API_KEY)
- Check API quota and billing status
- Review logs for API errors

### Getting Help

- Create an issue on GitHub
- Check the [Agno documentation](https://docs.agno.com)
- Join our community discussions

---

**Built with the Agno Framework**

Transform your financial management with intelligent AI agents that understand your spending habits and help you achieve your financial goals!