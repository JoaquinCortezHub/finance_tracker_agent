import asyncio
import logging
import sys
from pathlib import Path
from finance_tracker_agent.workflows.finance_workflow import FinanceTrackerWorkflow
from finance_tracker_agent.config.settings import settings


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('finance_tracker.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def check_prerequisites():
    """Check if all prerequisites are met."""
    errors = []
    
    # Check for required environment variables
    if not settings.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN not configured")
    
    if not settings.anthropic_api_key and not settings.openai_api_key:
        errors.append("No AI model API key configured (ANTHROPIC_API_KEY or OPENAI_API_KEY)")
    
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    return errors


async def main():
    """Main application entry point."""
    print("🤖 Finance Tracker Agent")
    print("=" * 50)
    
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check prerequisites
    errors = check_prerequisites()
    if errors:
        print("\n❌ Configuration errors:")
        for error in errors:
            print(f"   • {error}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("Use .env.template as a reference.")
        return
    
    print("✅ Configuration validated")
    
    try:
        # Initialize the workflow
        print("🔧 Initializing Finance Tracker Workflow...")
        workflow = FinanceTrackerWorkflow()
        
        # Show system status
        status = workflow.get_system_status()
        print(f"\n📊 System Status:")
        print(f"   • Excel file: {'✅' if status['excel_file_exists'] else '❌'}")
        print(f"   • Telegram: {'✅' if status['telegram_configured'] else '❌'}")
        print(f"   • AI Model: {'✅' if status['ai_model_configured'] else '❌'}")
        print(f"   • Agents loaded: {'✅' if all(status['agents_loaded'].values()) else '❌'}")
        
        if settings.telegram_chat_id:
            print(f"   • Default chat ID: {settings.telegram_chat_id}")
        
        print(f"\n🚀 Starting Telegram bot...")
        print(f"📱 Bot will respond to messages in Telegram")
        print(f"💰 Excel file: {settings.excel_file_path}")
        print(f"\nPress Ctrl+C to stop the bot")
        print("-" * 50)
        
        # Start the bot
        await workflow.start_telegram_bot()
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Finance Tracker Agent...")
        logger.info("Application shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        print("Check the log file (finance_tracker.log) for more details")
    finally:
        print("✅ Finance Tracker Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
