# app/config/payment_config.py
from pydantic_settings import BaseSettings
from typing import Optional
import os

class PaymentSettings(BaseSettings):
    """Payment configuration settings."""
    
    # Stripe Configuration
    stripe_secret_key: str = "sk_test_your_stripe_secret_key_here"
    stripe_publishable_key: str = "pk_test_your_stripe_publishable_key_here"
    stripe_webhook_secret: str = "whsec_your_webhook_secret_here"
    
    # Payment defaults
    default_currency: str = "usd"
    minimum_payment_amount: float = 0.50  # Minimum $0.50
    maximum_payment_amount: float = 1000.00  # Maximum $1000
    
    # Environment
    environment: str = "test"  # "test" or "live"
    
    class Config:
        env_file = ".env"
        env_prefix = "PAYMENT_"

# Global payment settings instance
payment_settings = PaymentSettings()

def configure_stripe():
    """Configure Stripe with settings."""
    import stripe
    stripe.api_key = payment_settings.stripe_secret_key
    return stripe