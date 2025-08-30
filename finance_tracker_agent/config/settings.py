from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings and configuration."""
    
    # Telegram Bot Configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, env="TELEGRAM_CHAT_ID")
    
    # OpenAI/Anthropic Configuration
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    
    # Excel Configuration
    excel_file_path: Path = Field(
        default_factory=lambda: Path("data/finance_tracker.xlsx"),
        env="EXCEL_FILE_PATH"
    )
    
    # Database Configuration (for agent memory/storage)
    database_url: str = Field(
        default="sqlite:///data/finance_agent.db",
        env="DATABASE_URL"
    )
    
    # Application Settings
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Financial Settings
    default_currency: str = Field(default="USD", env="DEFAULT_CURRENCY")
    expense_categories: list[str] = Field(
        default=[
            "Food & Dining",
            "Transportation", 
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Education",
            "Travel",
            "Savings & Investment",
            "Other"
        ]
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()