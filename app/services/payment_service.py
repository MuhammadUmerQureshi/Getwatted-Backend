# app/services/payment_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import stripe
from fastapi import HTTPException

from app.db.database import execute_query, execute_insert, execute_update
from app.models.payment_method import PaymentTransactionCreate

logger = logging.getLogger("ocpp.payment")


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
        driver_id: Optional[int] = None,
        company_id: Optional[int] = None
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
        
    @staticmethod
    async def create_or_get_customer(user_id: int, email: str, first_name: str = None, last_name: str = None) -> str:
        """
        Create Stripe customer or get existing one for a user.
        
        Args:
            user_id: User ID from database
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            
        Returns:
            Stripe customer ID
        """
        try:
            # Check if customer already exists in database
            existing_customer = execute_query(
                """
                SELECT UserStripeCustomerStripeCustomerId 
                FROM UserStripeCustomers 
                WHERE UserStripeCustomerUserId = ?
                """,
                (user_id,)
            )
            
            if existing_customer:
                customer_id = existing_customer[0]["UserStripeCustomerStripeCustomerId"]
                logger.info(f"✅ Found existing Stripe customer: {customer_id} for user {user_id}")
                return customer_id
            
            # Create new Stripe customer
            customer_data = {
                "email": email,
                "metadata": {"user_id": str(user_id)}
            }
            
            if first_name or last_name:
                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if last_name:
                    name_parts.append(last_name)
                customer_data["name"] = " ".join(name_parts)
            
            customer = stripe.Customer.create(**customer_data)
            
            # Store customer ID in database
            execute_insert(
                """
                INSERT INTO UserStripeCustomers 
                (UserStripeCustomerUserId, UserStripeCustomerStripeCustomerId) 
                VALUES (?, ?)
                """,
                (user_id, customer.id)
            )
            
            logger.info(f"✅ Created new Stripe customer: {customer.id} for user {user_id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error creating customer: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error creating customer: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def save_payment_method(user_id: int, customer_id: str, payment_method_id: str, set_as_default: bool = False) -> Dict[str, Any]:
        """
        Save a payment method to customer and database.
        
        Args:
            user_id: User ID from database
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID
            set_as_default: Whether to set as default payment method
            
        Returns:
            Dictionary with saved payment method details
        """
        try:
            # Attach payment method to customer in Stripe
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Get payment method details
            card = payment_method.card
            
            # If setting as default, update existing default to false
            if set_as_default:
                execute_update(
                    """
                    UPDATE SavedPaymentMethods 
                    SET SavedPaymentMethodIsDefault = FALSE 
                    WHERE SavedPaymentMethodUserId = ?
                    """,
                    (user_id,)
                )
            
            # Save payment method in database
            execute_insert(
                """
                INSERT INTO SavedPaymentMethods 
                (SavedPaymentMethodUserId, SavedPaymentMethodStripePaymentMethodId, 
                 SavedPaymentMethodCardBrand, SavedPaymentMethodCardLastFour,
                 SavedPaymentMethodCardExpMonth, SavedPaymentMethodCardExpYear,
                 SavedPaymentMethodIsDefault) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, payment_method_id, card.brand, card.last4, 
                 card.exp_month, card.exp_year, set_as_default)
            )
            
            logger.info(f"✅ Saved payment method {payment_method_id} for user {user_id}")
            
            return {
                "payment_method_id": payment_method_id,
                "card_brand": card.brand,
                "card_last_four": card.last4,
                "card_exp_month": card.exp_month,
                "card_exp_year": card.exp_year,
                "is_default": set_as_default
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error saving payment method: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error saving payment method: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def create_payment_intent_with_customer(
        customer_id: str,
        amount: float,
        currency: str = "usd",
        description: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe payment intent with an existing customer.
        
        Args:
            customer_id: Stripe customer ID
            amount: Amount in currency units
            currency: Currency code
            description: Payment description
            payment_method_id: Specific payment method to use
            session_id: Associated session ID
            
        Returns:
            Dictionary with payment intent details
        """
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Create metadata
            metadata = {"customer_id": customer_id}
            if session_id:
                metadata["session_id"] = str(session_id)
            
            # Prepare intent data
            intent_data = {
                "amount": amount_cents,
                "currency": currency,
                "customer": customer_id,
                "description": description,
                "metadata": metadata,
                "automatic_payment_methods": {"enabled": True}
            }
            
            # If specific payment method provided, use it
            if payment_method_id:
                intent_data["payment_method"] = payment_method_id
                intent_data["confirmation_method"] = "manual"
                intent_data["confirm"] = True
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(**intent_data)
            
            logger.info(f"✅ Payment intent created with customer: {intent.id} for amount ${amount}")
            
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error creating payment intent with customer: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error creating payment intent with customer: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def get_saved_payment_methods(user_id: int) -> List[Dict[str, Any]]:
        """
        Get all saved payment methods for a user.
        
        Args:
            user_id: User ID from database
            
        Returns:
            List of saved payment methods
        """
        try:
            payment_methods = execute_query(
                """
                SELECT SavedPaymentMethodId, SavedPaymentMethodStripePaymentMethodId,
                       SavedPaymentMethodCardBrand, SavedPaymentMethodCardLastFour,
                       SavedPaymentMethodCardExpMonth, SavedPaymentMethodCardExpYear,
                       SavedPaymentMethodIsDefault, SavedPaymentMethodCreated
                FROM SavedPaymentMethods 
                WHERE SavedPaymentMethodUserId = ?
                ORDER BY SavedPaymentMethodIsDefault DESC, SavedPaymentMethodCreated DESC
                """,
                (user_id,)
            )
            
            return [
                {
                    "id": pm["SavedPaymentMethodId"],
                    "payment_method_id": pm["SavedPaymentMethodStripePaymentMethodId"],
                    "card_brand": pm["SavedPaymentMethodCardBrand"],
                    "card_last_four": pm["SavedPaymentMethodCardLastFour"],
                    "card_exp_month": pm["SavedPaymentMethodCardExpMonth"],
                    "card_exp_year": pm["SavedPaymentMethodCardExpYear"],
                    "is_default": pm["SavedPaymentMethodIsDefault"],
                    "created_at": pm["SavedPaymentMethodCreated"]
                }
                for pm in payment_methods
            ]
            
        except Exception as e:
            logger.error(f"❌ Error getting saved payment methods: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def delete_saved_payment_method(user_id: int, payment_method_id: str) -> bool:
        """
        Delete a saved payment method.
        
        Args:
            user_id: User ID from database
            payment_method_id: Stripe payment method ID to delete
            
        Returns:
            True if successful
        """
        try:
            # Detach from Stripe customer
            stripe.PaymentMethod.detach(payment_method_id)
            
            # Remove from database
            execute_update(
                """
                DELETE FROM SavedPaymentMethods 
                WHERE SavedPaymentMethodUserId = ? AND SavedPaymentMethodStripePaymentMethodId = ?
                """,
                (user_id, payment_method_id)
            )
            
            logger.info(f"✅ Deleted payment method {payment_method_id} for user {user_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error deleting payment method: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error deleting payment method: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def create_payment_intent_for_saving(
        customer_id: str,
        amount: float,
        currency: str = "usd",
        description: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a payment intent that's designed for saving payment methods.
        This creates the intent with the customer from the start.
        
        Args:
            customer_id: Stripe customer ID
            amount: Amount in currency units
            currency: Currency code
            description: Payment description
            session_id: Associated session ID
            
        Returns:
            Dictionary with payment intent details
        """
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Create metadata
            metadata = {"customer_id": customer_id}
            if session_id:
                metadata["session_id"] = str(session_id)
            
            # Create payment intent with customer
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                customer=customer_id,
                description=description,
                metadata=metadata,
                setup_future_usage="off_session",  # This enables saving for future use
                automatic_payment_methods={"enabled": True}
            )
            
            logger.info(f"✅ Payment intent created for saving: {intent.id} for amount ${amount}")
            
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error creating payment intent for saving: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error creating payment intent for saving: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")

    @staticmethod
    async def save_payment_method_from_intent(
        user_id: int,
        payment_intent_id: str,
        set_as_default: bool = False
    ) -> Dict[str, Any]:
        """
        Save payment method from a completed payment intent.
        This extracts the payment method from the intent and saves it.
        
        Args:
            user_id: User ID from database
            payment_intent_id: Completed payment intent ID
            set_as_default: Whether to set as default
            
        Returns:
            Dictionary with saved payment method details
        """
        try:
            # Retrieve the payment intent
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if not intent.payment_method:
                raise HTTPException(status_code=400, detail="No payment method found on intent")
            
            # Get payment method details
            payment_method = stripe.PaymentMethod.retrieve(intent.payment_method)
            
            # Check if already attached to customer
            if not payment_method.customer:
                # Get customer ID for user
                customer_result = execute_query(
                    """
                    SELECT UserStripeCustomerStripeCustomerId 
                    FROM UserStripeCustomers 
                    WHERE UserStripeCustomerUserId = ?
                    """,
                    (user_id,)
                )
                
                if not customer_result:
                    raise HTTPException(status_code=400, detail="No customer found for user")
                
                customer_id = customer_result[0]["UserStripeCustomerStripeCustomerId"]
                
                # Attach to customer
                stripe.PaymentMethod.attach(
                    payment_method.id,
                    customer=customer_id
                )
            
            # Save in database
            card = payment_method.card
            
            # If setting as default, update existing default to false
            if set_as_default:
                execute_update(
                    """
                    UPDATE SavedPaymentMethods 
                    SET SavedPaymentMethodIsDefault = FALSE 
                    WHERE SavedPaymentMethodUserId = ?
                    """,
                    (user_id,)
                )
            
            # Check if already saved
            existing_pm = execute_query(
                """
                SELECT SavedPaymentMethodId 
                FROM SavedPaymentMethods 
                WHERE SavedPaymentMethodStripePaymentMethodId = ?
                """,
                (payment_method.id,)
            )
            
            if not existing_pm:
                # Save payment method in database
                execute_insert(
                    """
                    INSERT INTO SavedPaymentMethods 
                    (SavedPaymentMethodUserId, SavedPaymentMethodStripePaymentMethodId, 
                     SavedPaymentMethodCardBrand, SavedPaymentMethodCardLastFour,
                     SavedPaymentMethodCardExpMonth, SavedPaymentMethodCardExpYear,
                     SavedPaymentMethodIsDefault) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, payment_method.id, card.brand, card.last4, 
                     card.exp_month, card.exp_year, set_as_default)
                )
            
            logger.info(f"✅ Saved payment method from intent {payment_intent_id} for user {user_id}")
            
            return {
                "payment_method_id": payment_method.id,
                "card_brand": card.brand,
                "card_last_four": card.last4,
                "card_exp_month": card.exp_month,
                "card_exp_year": card.exp_year,
                "is_default": set_as_default
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error saving payment method from intent: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error saving payment method from intent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal payment service error")