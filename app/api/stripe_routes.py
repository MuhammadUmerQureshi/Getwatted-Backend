# app/api/stripe_routes.py
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import stripe
import json
import logging
from datetime import datetime

from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1/stripe", tags=["stripe_payments"])
logger = logging.getLogger("ocpp.stripe")

# Pydantic models for request validation
class CreatePaymentIntentRequest(BaseModel):
    amount: float  # Amount in currency units (e.g., dollars)
    currency: str = "usd"
    description: Optional[str] = None
    session_id: Optional[int] = None
    driver_id: Optional[int] = None

class CreateSessionPaymentRequest(BaseModel):
    session_id: int
    payment_method_id: int
    amount: Optional[float] = None  # If not provided, will use session cost
    description: Optional[str] = None

# Set your Stripe webhook secret here
WEBHOOK_SECRET = "your_webhook_secret_here"  # Set this in environment variables

@router.post("/create-payment-intent")
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """Create a Stripe payment intent."""
    try:
        result = await PaymentService.create_payment_intent(
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            session_id=request.session_id,
            driver_id=request.driver_id
        )
        
        logger.info(f"💳 Payment intent created: {result['payment_intent_id']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error creating payment intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payment-intent/{payment_intent_id}")
async def get_payment_intent(payment_intent_id: str):
    """Retrieve a Stripe payment intent."""
    try:
        result = await PaymentService.retrieve_payment_intent(payment_intent_id)
        return result
        
    except Exception as e:
        logger.error(f"❌ Error retrieving payment intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-session-payment")
async def create_session_payment(request: CreateSessionPaymentRequest):
    """Create a payment intent for a specific charge session."""
    try:
        from app.db.database import execute_query
        
        # First, check if a payment intent already exists for this session
        existing_payment = execute_query(
            """SELECT pt.PaymentTransactionId, pt.PaymentTransactionStripeIntentId, pt.PaymentTransactionStatus, pt.PaymentTransactionAmount
               FROM PaymentTransactions pt 
               WHERE pt.PaymentTransactionSessionId = ? 
               AND pt.PaymentTransactionStripeIntentId IS NOT NULL
               ORDER BY pt.PaymentTransactionCreated DESC 
               LIMIT 1""",
            (request.session_id,)
        )
        
        if existing_payment:
            existing_intent_id = existing_payment[0]["PaymentTransactionStripeIntentId"]
            existing_status = existing_payment[0]["PaymentTransactionStatus"]
            existing_amount = existing_payment[0]["PaymentTransactionAmount"]
            
            # If payment is already completed, return error
            if existing_status in ["completed", "succeeded", "paid"]:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Payment already completed for session {request.session_id}"
                )
            
            # If payment exists but is pending, retrieve the existing intent
            try:
                existing_intent = stripe.PaymentIntent.retrieve(existing_intent_id)
                
                # If the intent is still valid and can be used
                if existing_intent.status in ["requires_payment_method", "requires_confirmation"]:
                    logger.info(f"🔄 Returning existing payment intent: {existing_intent_id}")
                    return {
                        "transaction_id": existing_payment[0].get("PaymentTransactionId"),
                        "payment_intent": {
                            "payment_intent_id": existing_intent.id,
                            "client_secret": existing_intent.client_secret,
                            "amount": existing_intent.amount,
                            "currency": existing_intent.currency,
                            "status": existing_intent.status
                        },
                        "session_id": request.session_id,
                        "amount": existing_amount
                    }
                    
            except stripe.error.StripeError as e:
                logger.warning(f"⚠️ Could not retrieve existing intent {existing_intent_id}: {e}")
                # Continue to create new intent if existing one is invalid
        
        # Get session details
        session = execute_query(
            "SELECT ChargerSessionCost, ChargerSessionEnergyKWH FROM ChargeSessions WHERE ChargeSessionId = ?",
            (request.session_id,)
        )
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        
        session_data = session[0]
        
        # Use provided amount or session cost
        amount = request.amount if request.amount is not None else session_data.get("ChargerSessionCost", 0)
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid payment amount")
        
        # Create new payment intent
        payment_intent = await PaymentService.create_payment_intent(
            amount=amount,
            description=request.description or f"Payment for charge session {request.session_id}",
            session_id=request.session_id
        )
        
        # Create payment transaction record
        transaction_id = await PaymentService.create_payment_transaction_from_session(
            session_id=request.session_id,
            payment_method_id=request.payment_method_id,
            amount=amount,
            stripe_intent_id=payment_intent["payment_intent_id"],
            status="pending"
        )
        
        logger.info(f"💳 New session payment created: Transaction {transaction_id}, Intent {payment_intent['payment_intent_id']}")
        
        return {
            "transaction_id": transaction_id,
            "payment_intent": payment_intent,
            "session_id": request.session_id,
            "amount": amount
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating session payment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"❌ Invalid webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ Invalid webhook signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Log the event
        logger.info(f"🎯 Webhook received: {event['type']} - {event['id']}")
        
        # Handle the event
        success = await PaymentService.handle_stripe_webhook(
            event_type=event["type"],
            event_data=event["data"]
        )
        
        if success:
            return {"status": "success", "event_type": event["type"]}
        else:
            raise HTTPException(status_code=500, detail="Failed to process webhook")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@router.get("/recent-payments")
async def get_recent_stripe_payments(limit: int = 10):
    """Get recent Stripe payments for debugging."""
    try:
        payments = stripe.PaymentIntent.list(limit=limit)
        
        result = []
        for payment in payments.data:
            result.append({
                "id": payment.id,
                "amount": payment.amount / 100,  # Convert from cents
                "currency": payment.currency,
                "status": payment.status,
                "created": datetime.fromtimestamp(payment.created).isoformat(),
                "description": payment.description,
                "metadata": payment.metadata
            })
        
        return {"payments": result}
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refund/{payment_intent_id}")
async def refund_payment(payment_intent_id: str, amount: Optional[float] = None):
    """Refund a payment (full or partial)."""
    try:
        # Get the payment intent
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status != "succeeded":
            raise HTTPException(status_code=400, detail="Payment not succeeded, cannot refund")
        
        # Calculate refund amount
        refund_amount = None
        if amount is not None:
            refund_amount = int(amount * 100)  # Convert to cents
        
        # Create refund
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=refund_amount
        )
        
        # Update transaction status
        await PaymentService.update_payment_status(
            stripe_intent_id=payment_intent_id,
            status="refunded"
        )
        
        logger.info(f"💰 Refund created: {refund.id} for payment {payment_intent_id}")
        
        return {
            "refund_id": refund.id,
            "amount": refund.amount / 100,
            "status": refund.status,
            "payment_intent_id": payment_intent_id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe refund error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Refund error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))