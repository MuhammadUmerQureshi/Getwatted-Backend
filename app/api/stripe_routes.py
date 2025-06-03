# app/api/stripe_routes.py
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel
from typing import Optional
import stripe
import logging
import json
from datetime import datetime

from app.services.payment_service import PaymentService
from app.db.database import execute_query, execute_update
from app.models.auth import UserInToken
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_company_access,
    require_admin_or_higher
)

router = APIRouter(prefix="/api/v1/stripe", tags=["STRIPE_PAYMENTS"])
logger = logging.getLogger("ocpp.stripe")

# Pydantic models for request validation
class CreatePaymentIntentRequest(BaseModel):
    amount: float  # Amount in currency units (e.g., dollars)
    currency: str = "usd"
    description: Optional[str] = None
    session_id: Optional[int] = None  # Session ID to link payment transaction
    company_id: Optional[int] = None  # Company ID for the payment

class CreatePaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    status: str = "created"

# Set your Stripe webhook secret here - REPLACE WITH YOUR ACTUAL SECRET
WEBHOOK_SECRET = "whsec_DXsICWF7x2vcEXkQMBUUmjeESlLPJsZP"

# Stripe PaymentIntent Status Reference:
# - requires_payment_method: Needs a payment method attached
# - requires_confirmation: Payment method attached, needs confirmation  
# - requires_action: Additional action required (e.g., 3D Secure authentication)
# - requires_capture: Payment authorized but not yet captured
# - processing: Payment is being processed (async payment methods)
# - succeeded: Payment completed successfully
# - canceled: Payment was canceled

@router.post("/create-payment-intent", response_model=CreatePaymentIntentResponse)
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    user: UserInToken = Depends(get_current_user)
):
    """
    Create a Stripe payment intent with payment transaction status checking and linking.
    
    - SuperAdmin: Can create payment intents for any company
    - Admin: Can only create payment intents for their company
    - Driver: Can only create payment intents for their own sessions
    """
    try:
        # Validate company access
        if user.role.value == "Driver":
            if request.session_id:
                # Verify session belongs to driver
                session = execute_query(
                    """
                    SELECT ChargerSessionDriverId, ChargerSessionCompanyId 
                    FROM ChargeSessions 
                    WHERE ChargeSessionId = ?
                    """,
                    (request.session_id,)
                )
                if not session or session[0]["ChargerSessionDriverId"] != user.driver_id:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only create payment intents for your own sessions"
                    )
                request.company_id = session[0]["ChargerSessionCompanyId"]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Session ID is required for driver payments"
                )
        elif user.role.value == "Admin":
            if request.company_id and request.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create payment intents for your company"
                )
            request.company_id = user.company_id
        elif user.role.value == "SuperAdmin":
            if not request.company_id:
                raise HTTPException(
                    status_code=400,
                    detail="Company ID is required for payment intent creation"
                )

        existing_transaction = None
        
        # 1. Check existing payment transaction status if session_id is provided
        if request.session_id:
            existing_transaction = execute_query(
                """
                SELECT PaymentTransactionId, PaymentTransactionPaymentStatus, 
                       PaymentTransactionStripeIntentId, PaymentTransactionAmount,
                       PaymentTransactionCompanyId
                FROM PaymentTransactions 
                WHERE PaymentTransactionSessionId = ?
                ORDER BY PaymentTransactionCreated DESC LIMIT 1
                """,
                (request.session_id,)
            )
            
            if existing_transaction:
                transaction_data = existing_transaction[0]
                payment_status = transaction_data["PaymentTransactionPaymentStatus"]
                stripe_intent_id = transaction_data["PaymentTransactionStripeIntentId"]
                transaction_company_id = transaction_data["PaymentTransactionCompanyId"]
                
                # Verify company access for existing transaction
                if user.role.value == "Admin" and transaction_company_id != user.company_id:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only access payment intents for your company"
                    )
                
                # 1. If status is succeeded, don't process again
                if payment_status == "completed":
                    logger.info(f"🚫 Payment already succeeded for session {request.session_id}")
                    raise HTTPException(
                        status_code=400, 
                        detail="Payment already completed for this session"
                    )
                
                # 2. If payment intent exists and status is not succeeded, try to reuse same intent
                if stripe_intent_id and payment_status != "completed":
                    try:
                        # Retrieve existing PaymentIntent from Stripe
                        intent = stripe.PaymentIntent.retrieve(stripe_intent_id)
                        
                        # Check if intent can be reused based on Stripe PaymentIntent statuses
                        reusable_statuses = [
                            'requires_payment_method', 
                            'requires_confirmation', 
                            'requires_action',
                            'requires_capture'
                        ]
                        
                        if intent.status in reusable_statuses:
                            # Update amount if different (convert to cents)
                            amount_cents = int(request.amount * 100)
                            if intent.amount != amount_cents:
                                intent = stripe.PaymentIntent.modify(
                                    stripe_intent_id,
                                    amount=amount_cents,
                                )
                            
                            logger.info(f"🔄 Reusing existing payment intent: {intent.id} (status: {intent.status})")
                            return CreatePaymentIntentResponse(
                                client_secret=intent.client_secret,
                                payment_intent_id=intent.id,
                                status="reused"
                            )
                        else:
                            logger.info(f"⚠️ Intent {stripe_intent_id} status '{intent.status}' cannot be reused")
                            
                    except stripe.error.StripeError as e:
                        logger.warning(f"⚠️ Could not retrieve intent {stripe_intent_id}: {e}")
                        # Continue to create new intent if reuse fails
        
        # 2. Create new payment intent
        result = await PaymentService.create_payment_intent(
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            session_id=request.session_id,
            company_id=request.company_id
        )
        
        # 3. CRITICAL FIX: Link the Stripe intent ID to existing payment transaction
        if request.session_id and existing_transaction:
            transaction_id = existing_transaction[0]["PaymentTransactionId"]
            
            # Update the existing transaction with Stripe intent ID
            execute_update(
                """
                UPDATE PaymentTransactions 
                SET PaymentTransactionStripeIntentId = ?, PaymentTransactionUpdated = ?
                WHERE PaymentTransactionId = ?
                """,
                (result['payment_intent_id'], datetime.now().isoformat(), transaction_id)
            )
            
            logger.info(f"✅ Linked Stripe intent {result['payment_intent_id']} to transaction {transaction_id}")
        
        logger.info(f"💳 New payment intent created: {result['payment_intent_id']}")
        return CreatePaymentIntentResponse(
            client_secret=result['client_secret'],
            payment_intent_id=result['payment_intent_id'],
            status="created"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating payment intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payment-intent/{payment_intent_id}")
async def get_payment_intent(
    payment_intent_id: str,
    user: UserInToken = Depends(get_current_user)
):
    """
    Retrieve a Stripe payment intent.
    
    - SuperAdmin: Can retrieve any payment intent
    - Admin: Can only retrieve payment intents from their company
    - Driver: Can only retrieve payment intents for their own sessions
    """
    try:
        # Get transaction details to verify access
        transaction = execute_query(
            """
            SELECT PaymentTransactionCompanyId, PaymentTransactionDriverId, PaymentTransactionSessionId
            FROM PaymentTransactions 
            WHERE PaymentTransactionStripeIntentId = ?
            """,
            (payment_intent_id,)
        )
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail=f"Payment intent {payment_intent_id} not found"
            )
            
        # Verify access based on role
        if user.role.value == "Driver":
            if transaction[0]["PaymentTransactionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view payment intents for your own sessions"
                )
        elif user.role.value == "Admin":
            if transaction[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view payment intents from your company"
                )
        
        result = await PaymentService.retrieve_payment_intent(payment_intent_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving payment intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    This endpoint is public and secured by Stripe webhook signature verification.
    """
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

