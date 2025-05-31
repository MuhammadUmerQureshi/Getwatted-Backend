# app/models/payment_method.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PaymentMethodCreate(BaseModel):
    """Schema for creating a new payment method."""
    PaymentMethodName: str
    PaymentMethodCompanyId: int
    PaymentMethodEnabled: bool = True


class PaymentMethodUpdate(BaseModel):
    """Schema for updating a payment method."""
    PaymentMethodName: Optional[str] = None
    PaymentMethodEnabled: Optional[bool] = None


class PaymentMethod(BaseModel):
    """Payment method model representing a payment method in the database."""
    PaymentMethodId: int
    PaymentMethodCompanyId: int
    PaymentMethodName: str
    PaymentMethodEnabled: bool
    PaymentMethodCreated: datetime
    PaymentMethodUpdated: datetime

    class Config:
        from_attributes = True


class PaymentTransactionCreate(BaseModel):
    """Schema for creating a new payment transaction."""
    PaymentTransactionMethodUsed: int
    PaymentTransactionDriverId: Optional[int] = None
    PaymentTransactionAmount: float
    PaymentTransactionStatus: str = "pending"
    PaymentTransactionPaymentStatus: str = "pending"  # NEW: Actual payment status
    PaymentTransactionCompanyId: int
    PaymentTransactionSiteId: int
    PaymentTransactionChargerId: int
    PaymentTransactionSessionId: Optional[int] = None
    PaymentTransactionStripeIntentId: Optional[str] = None


class PaymentTransactionUpdate(BaseModel):
    """Schema for updating a payment transaction."""
    PaymentTransactionStatus: Optional[str] = None
    PaymentTransactionPaymentStatus: Optional[str] = None  # NEW: Update payment status
    PaymentTransactionAmount: Optional[float] = None
    PaymentTransactionStripeIntentId: Optional[str] = None


class PaymentTransaction(BaseModel):
    """Payment transaction model representing a payment transaction in the database."""
    PaymentTransactionId: int
    PaymentTransactionMethodUsed: int
    PaymentTransactionDriverId: Optional[int] = None
    PaymentTransactionDateTime: datetime
    PaymentTransactionAmount: float
    PaymentTransactionStatus: str
    PaymentTransactionPaymentStatus: str  # NEW: Actual payment status
    PaymentTransactionCompanyId: int
    PaymentTransactionSiteId: int
    PaymentTransactionChargerId: int
    PaymentTransactionSessionId: Optional[int] = None
    PaymentTransactionStripeIntentId: Optional[str] = None
    PaymentTransactionCreated: datetime
    PaymentTransactionUpdated: datetime

    class Config:
        from_attributes = True