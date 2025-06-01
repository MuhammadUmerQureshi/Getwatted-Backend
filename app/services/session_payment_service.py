# app/services/session_payment_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from app.db.database import execute_query, execute_update, execute_insert

logger = logging.getLogger("ocpp.session_payment")

class SessionPaymentService:
    """Service for managing payment status synchronization between sessions and transactions."""
    
    @staticmethod
    async def update_session_payment_status(
        session_id: int,
        payment_transaction_id: int,
        payment_status: str
    ) -> bool:
        """
        Update the charge session with payment information.
        
        Args:
            session_id: Charge session ID
            payment_transaction_id: Payment transaction ID
            payment_status: Payment status (pending, succeeded, failed, canceled, refunded)
            
        Returns:
            True if successful
        """
        try:
            # Update the charge session with payment information
            execute_update(
                """
                UPDATE ChargeSessions 
                SET ChargerSessionPaymentId = ?, ChargerSessionPaymentStatus = ?
                WHERE ChargeSessionId = ?
                """,
                (payment_transaction_id, payment_status, session_id)
            )
            
            logger.info(f"✅ Session {session_id} payment status updated to {payment_status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating session payment status: {str(e)}")
            return False
    
    @staticmethod
    async def update_payment_transaction_status(
        transaction_id: Optional[int] = None,
        stripe_intent_id: Optional[str] = None,
        payment_status: str = "succeeded"
    ) -> bool:
        """
        Update payment transaction status and sync with charge session.
        Enhanced version that maintains session synchronization.
        
        Args:
            transaction_id: Payment transaction ID
            stripe_intent_id: Stripe payment intent ID (alternative lookup)
            payment_status: New payment status
            
        Returns:
            True if successful
        """
        try:
            now = datetime.now().isoformat()
            session_id = None
            
            # Get transaction details including session ID
            if transaction_id:
                transaction = execute_query(
                    "SELECT PaymentTransactionSessionId FROM PaymentTransactions WHERE PaymentTransactionId = ?",
                    (transaction_id,)
                )
                
                if transaction:
                    # Update payment transaction
                    execute_update(
                        """
                        UPDATE PaymentTransactions 
                        SET PaymentTransactionPaymentStatus = ?, PaymentTransactionUpdated = ?
                        WHERE PaymentTransactionId = ?
                        """,
                        (payment_status, now, transaction_id)
                    )
                    
                    session_id = transaction[0]["PaymentTransactionSessionId"]
                    
            elif stripe_intent_id:
                transaction = execute_query(
                    "SELECT PaymentTransactionId, PaymentTransactionSessionId FROM PaymentTransactions WHERE PaymentTransactionStripeIntentId = ?",
                    (stripe_intent_id,)
                )
                
                if transaction:
                    transaction_id = transaction[0]["PaymentTransactionId"]
                    session_id = transaction[0]["PaymentTransactionSessionId"]
                    
                    # Update payment transaction
                    execute_update(
                        """
                        UPDATE PaymentTransactions 
                        SET PaymentTransactionPaymentStatus = ?, PaymentTransactionUpdated = ?
                        WHERE PaymentTransactionStripeIntentId = ?
                        """,
                        (payment_status, now, stripe_intent_id)
                    )
            else:
                raise ValueError("Either transaction_id or stripe_intent_id must be provided")
            
            # Update associated charge session if exists
            if session_id:
                # Import the sync service
                from app.services.payment_sync_service import PaymentSyncService
                
                # Map payment status to session status
                session_payment_status = PaymentSyncService._map_payment_status(payment_status)
                
                # Update session
                execute_update(
                    """
                    UPDATE ChargeSessions 
                    SET ChargerSessionPaymentStatus = ?, ChargerSessionPaymentId = ?, ChargerSessionPaymentAmount = ?
                    WHERE ChargeSessionId = ?
                    """,
                    (
                        session_payment_status,
                        transaction_id,
                        execute_query(
                            "SELECT PaymentTransactionAmount FROM PaymentTransactions WHERE PaymentTransactionId = ?",
                            (transaction_id,)
                        )[0]["PaymentTransactionAmount"] if transaction_id else None,
                        session_id
                    )
                )
                
                logger.info(f"✅ Session {session_id} payment status updated to {session_payment_status}")
            
            logger.info(f"✅ Payment transaction {transaction_id} status updated to {payment_status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating payment transaction status: {str(e)}")
            return False
    
    @staticmethod
    async def get_session_payment_status(session_id: int) -> Dict[str, Any]:
        """
        Get comprehensive payment status for a charge session.
        
        Args:
            session_id: Charge session ID
            
        Returns:
            Dictionary with payment status information
        """
        try:
            # Get session payment information
            session_payment = execute_query(
                """
                SELECT ChargerSessionPaymentId, ChargerSessionPaymentStatus, ChargerSessionCost
                FROM ChargeSessions 
                WHERE ChargeSessionId = ?
                """,
                (session_id,)
            )
            
            if not session_payment:
                return {"error": "Session not found"}
            
            session_data = session_payment[0]
            payment_id = session_data["ChargerSessionPaymentId"]
            
            result = {
                "session_id": session_id,
                "session_payment_status": session_data["ChargerSessionPaymentStatus"],
                "session_cost": session_data["ChargerSessionCost"],
                "payment_transaction_id": payment_id,
                "payment_required": session_data["ChargerSessionCost"] and session_data["ChargerSessionCost"] > 0
            }
            
            # Get detailed payment transaction information if exists
            if payment_id:
                transaction = execute_query(
                    """
                    SELECT PaymentTransactionAmount, PaymentTransactionPaymentStatus, 
                           PaymentTransactionStripeIntentId, PaymentTransactionDateTime,
                           PaymentTransactionMethodUsed
                    FROM PaymentTransactions 
                    WHERE PaymentTransactionId = ?
                    """,
                    (payment_id,)
                )
                
                if transaction:
                    transaction_data = transaction[0]
                    result.update({
                        "transaction_amount": transaction_data["PaymentTransactionAmount"],
                        "transaction_payment_status": transaction_data["PaymentTransactionPaymentStatus"],
                        "stripe_intent_id": transaction_data["PaymentTransactionStripeIntentId"],
                        "payment_datetime": transaction_data["PaymentTransactionDateTime"],
                        "payment_method_id": transaction_data["PaymentTransactionMethodUsed"]
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting session payment status: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    async def mark_session_as_paid(session_id: int, payment_transaction_id: int) -> bool:
        """
        Mark a session as fully paid and update status.
        
        Args:
            session_id: Charge session ID
            payment_transaction_id: Payment transaction ID
            
        Returns:
            True if successful
        """
        try:
            return await SessionPaymentService.update_session_payment_status(
                session_id=session_id,
                payment_transaction_id=payment_transaction_id,
                payment_status="succeeded"
            )
            
        except Exception as e:
            logger.error(f"❌ Error marking session as paid: {str(e)}")
            return False
    
    @staticmethod
    async def get_unpaid_sessions(
        company_id: Optional[int] = None,
        site_id: Optional[int] = None,
        charger_id: Optional[int] = None,
        limit: int = 100
    ) -> list:
        """
        Get sessions that require payment but haven't been paid.
        
        Args:
            company_id: Filter by company
            site_id: Filter by site
            charger_id: Filter by charger
            limit: Maximum results
            
        Returns:
            List of unpaid sessions
        """
        try:
            query = """
                SELECT ChargeSessionId, ChargerSessionCompanyId, ChargerSessionSiteId, 
                       ChargerSessionChargerId, ChargerSessionCost, ChargerSessionPaymentStatus,
                       ChargerSessionStart, ChargerSessionEnd
                FROM ChargeSessions 
                WHERE ChargerSessionCost > 0 
                AND (ChargerSessionPaymentStatus IS NULL 
                     OR ChargerSessionPaymentStatus IN ('not_required', 'pending', 'failed'))
            """
            params = []
            
            if company_id:
                query += " AND ChargerSessionCompanyId = ?"
                params.append(company_id)
                
            if site_id:
                query += " AND ChargerSessionSiteId = ?"
                params.append(site_id)
                
            if charger_id:
                query += " AND ChargerSessionChargerId = ?"
                params.append(charger_id)
            
            query += " ORDER BY ChargerSessionEnd DESC LIMIT ?"
            params.append(limit)
            
            unpaid_sessions = execute_query(query, tuple(params))
            return unpaid_sessions
            
        except Exception as e:
            logger.error(f"❌ Error getting unpaid sessions: {str(e)}")
            return []