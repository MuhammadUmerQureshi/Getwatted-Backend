# app/services/payment_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import stripe
from fastapi import HTTPException

from app.db.database import execute_query, execute_insert, execute_update
from app.models.payment_method import PaymentTransactionCreate

logger = logging.getLogger("ocpp.payment")

# Configure Stripe (you should set this in environment variables)
# stripe.api_key = "your_stripe_secret_key_here"

class PaymentService:
    """Service for handling payment operations with Stripe integration."""
    
    @staticmethod
    def configure_stripe(api_key: str):
        """Configure Stripe with API key."""
        stripe.api_key = api_key
    
    @staticmethod
    async def create_payment_intent(
        amount: float,
        currency: str = "usd",
        description: Optional[str] = None,
        session_id: Optional[int] = None,
        driver_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe payment intent.
        
        Args:
            amount: Amount in currency units (e.g., dollars, not cents)
            currency: Currency code (default: usd)
            description: Payment description
            session_id: Associated charge session ID
            driver_id: Associated driver ID
            
        Returns:
            Dictionary with payment intent details
        """
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Create metadata for tracking
            metadata = {}
            if session_id:
                metadata["session_id"] = str(session_id)
            if driver_id:
                metadata["driver_id"] = str(driver_id)
            if description:
                metadata["description"] = description
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                description=description,
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            
            logger.info(f"✅ Payment intent created: {intent.id} for amount ${amount}")
            
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error creating payment intent: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error creating payment intent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")
    
    @staticmethod
    async def retrieve_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        """
        Retrieve a Stripe payment intent.
        
        Args:
            payment_intent_id: Stripe payment intent ID
            
        Returns:
            Dictionary with payment intent details
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                "payment_intent_id": intent.id,
                "amount": intent.amount / 100,  # Convert from cents
                "currency": intent.currency,
                "status": intent.status,
                "description": intent.description,
                "metadata": intent.metadata
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error retrieving payment intent: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
    
    @staticmethod
    async def create_payment_transaction_from_session(
        session_id: int,
        payment_method_id: int,
        amount: float,
        stripe_intent_id: Optional[str] = None,
        status: str = "pending",
        payment_status: str = "pending"  # NEW: Separate payment status
    ) -> int:
        """
        Create a payment transaction record linked to a charge session.
        
        Args:
            session_id: Charge session ID
            payment_method_id: Payment method ID
            amount: Transaction amount
            stripe_intent_id: Stripe payment intent ID
            status: Transaction status
            
        Returns:
            Transaction ID
        """
        try:
            # Get session details
            session = execute_query(
                """
                SELECT ChargerSessionCompanyId, ChargerSessionSiteId, ChargerSessionChargerId, 
                       ChargerSessionDriverId
                FROM ChargeSessions 
                WHERE ChargeSessionId = ?
                """,
                (session_id,)
            )
            
            if not session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            session_data = session[0]
            
            # Create transaction record
            transaction_data = PaymentTransactionCreate(
                PaymentTransactionMethodUsed=payment_method_id,
                PaymentTransactionDriverId=session_data["ChargerSessionDriverId"],
                PaymentTransactionAmount=amount,
                PaymentTransactionStatus=status,
                PaymentTransactionPaymentStatus=payment_status,  # NEW: Set payment status
                PaymentTransactionCompanyId=session_data["ChargerSessionCompanyId"],
                PaymentTransactionSiteId=session_data["ChargerSessionSiteId"],
                PaymentTransactionChargerId=session_data["ChargerSessionChargerId"],
                PaymentTransactionSessionId=session_id,
                PaymentTransactionStripeIntentId=stripe_intent_id
            )
            
            # Get maximum transaction ID and increment by 1
            max_id_result = execute_query("SELECT MAX(PaymentTransactionId) as max_id FROM PaymentTransactions")
            new_id = 1
            if max_id_result and max_id_result[0]['max_id'] is not None:
                new_id = max_id_result[0]['max_id'] + 1
                
            now = datetime.now().isoformat()
            
            # Insert new payment transaction
            execute_insert(
                """
                INSERT INTO PaymentTransactions (
                    PaymentTransactionId, PaymentTransactionMethodUsed, PaymentTransactionDriverId,
                    PaymentTransactionDateTime, PaymentTransactionAmount, PaymentTransactionStatus,
                    PaymentTransactionPaymentStatus, PaymentTransactionCompanyId, PaymentTransactionSiteId, 
                    PaymentTransactionChargerId, PaymentTransactionSessionId, PaymentTransactionStripeIntentId,
                    PaymentTransactionCreated, PaymentTransactionUpdated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    transaction_data.PaymentTransactionMethodUsed,
                    transaction_data.PaymentTransactionDriverId,
                    now,
                    transaction_data.PaymentTransactionAmount,
                    transaction_data.PaymentTransactionStatus,
                    transaction_data.PaymentTransactionPaymentStatus,  # NEW: Include payment status
                    transaction_data.PaymentTransactionCompanyId,
                    transaction_data.PaymentTransactionSiteId,
                    transaction_data.PaymentTransactionChargerId,
                    transaction_data.PaymentTransactionSessionId,
                    transaction_data.PaymentTransactionStripeIntentId,
                    now,
                    now
                )
            )
            
            # Update the charge session with payment transaction reference
            from app.services.session_payment_service import SessionPaymentService
            await SessionPaymentService.update_session_payment_status(
                session_id=session_id,
                payment_transaction_id=new_id,
                payment_status=payment_status
            )
            
            logger.info(f"✅ Payment transaction created: ID {new_id} for session {session_id}")
            return new_id
            
        except Exception as e:
            logger.error(f"❌ Error creating payment transaction: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create payment transaction")
    
    @staticmethod
    async def update_payment_status(
        transaction_id: Optional[int] = None,
        stripe_intent_id: Optional[str] = None,
        payment_status: str = "completed"
    ) -> bool:
        """
        Update payment transaction status and sync with charge session.
        
        Args:
            transaction_id: Payment transaction ID
            stripe_intent_id: Stripe payment intent ID (alternative lookup)
            payment_status: New payment status
            
        Returns:
            True if successful
        """
        try:
            # Use the new SessionPaymentService for comprehensive status updates
            from app.services.session_payment_service import SessionPaymentService
            return await SessionPaymentService.update_payment_transaction_status(
                transaction_id=transaction_id,
                stripe_intent_id=stripe_intent_id,
                payment_status=payment_status
            )
            
        except Exception as e:
            logger.error(f"❌ Error updating payment status: {str(e)}")
            return False
    
    @staticmethod
    async def handle_stripe_webhook(event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Handle Stripe webhook events.
        
        Args:
            event_type: Stripe event type
            event_data: Event data
            
        Returns:
            True if handled successfully
        """
        try:
            if event_type == "payment_intent.succeeded":
                payment_intent = event_data["object"]
                stripe_intent_id = payment_intent["id"]
                
                # Update transaction status to completed
                await PaymentService.update_payment_status(
                    stripe_intent_id=stripe_intent_id,
                    payment_status="succeeded"
                )
                
                logger.info(f"✅ Payment succeeded webhook handled: {stripe_intent_id}")
                
            elif event_type == "payment_intent.payment_failed":
                payment_intent = event_data["object"]
                stripe_intent_id = payment_intent["id"]
                
                # Update transaction status to failed
                await PaymentService.update_payment_status(
                    stripe_intent_id=stripe_intent_id,
                    payment_status="failed"
                )
                
                logger.info(f"❌ Payment failed webhook handled: {stripe_intent_id}")
                
            elif event_type == "payment_intent.canceled":
                payment_intent = event_data["object"]
                stripe_intent_id = payment_intent["id"]
                
                # Update transaction status to canceled
                await PaymentService.update_payment_status(
                    stripe_intent_id=stripe_intent_id,
                    payment_status="canceled"
                )
                
                logger.info(f"🚫 Payment canceled webhook handled: {stripe_intent_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error handling webhook: {str(e)}")
            return False