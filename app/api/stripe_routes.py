# app/api/stripe_routes.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import stripe
import logging

from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1/stripe", tags=["STRIPE_PAYMENTS"])
logger = logging.getLogger("ocpp.stripe")

# Pydantic models for request validation
class CreatePaymentIntentRequest(BaseModel):
    amount: float  # Amount in currency units (e.g., dollars)
    currency: str = "usd"
    description: Optional[str] = None
    payment_intent_id: Optional[str] = None  # Optional: reuse existing intent

class CreatePaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str

# Set your Stripe webhook secret here
WEBHOOK_SECRET = "your_webhook_secret_here"  # Set this in environment variables

@router.post("/create-payment-intent", response_model=CreatePaymentIntentResponse)
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """Create a Stripe payment intent or reuse existing one."""
    try:
        # If payment_intent_id is provided, try to reuse existing intent
        if request.payment_intent_id:
            try:
                # Retrieve existing PaymentIntent
                intent = stripe.PaymentIntent.retrieve(request.payment_intent_id)
                
                # Check if intent can be reused
                if intent.status in ['requires_payment_method', 'requires_confirmation', 'requires_action']:
                    # Update amount if different (convert to cents)
                    amount_cents = int(request.amount * 100)
                    if intent.amount != amount_cents:
                        intent = stripe.PaymentIntent.modify(
                            request.payment_intent_id,
                            amount=amount_cents,
                        )
                    
                    logger.info(f"🔄 Reusing existing payment intent: {intent.id}")
                    return CreatePaymentIntentResponse(
                        client_secret=intent.client_secret,
                        payment_intent_id=intent.id
                    )
                else:
                    logger.info(f"⚠️ Intent {request.payment_intent_id} status {intent.status} cannot be reused")
                    
            except stripe.error.StripeError as e:
                logger.warning(f"⚠️ Could not retrieve intent {request.payment_intent_id}: {e}")
                # Continue to create new intent if reuse fails
        
        # Create new payment intent
        result = await PaymentService.create_payment_intent(
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )
        
        logger.info(f"💳 New payment intent created: {result['payment_intent_id']}")
        return CreatePaymentIntentResponse(
            client_secret=result['client_secret'],
            payment_intent_id=result['payment_intent_id']
        )
        
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