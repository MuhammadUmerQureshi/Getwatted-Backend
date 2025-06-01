# app/services/payment_sync_service.py
import logging
from datetime import datetime
from app.db.database import execute_query, execute_update

logger = logging.getLogger("ocpp.payment_sync")

class PaymentSyncService:
    """Service for synchronizing payment status between sessions and payment transactions."""
    
    @staticmethod
    async def sync_session_payment_status(session_id):
        """
        Sync payment status from payment transaction to session.
        Called when payment transaction status changes.
        
        Args:
            session_id (int): Charge session ID
            
        Returns:
            bool: True if successful
        """
        try:
            # Get the latest payment transaction for this session
            payment_transaction = execute_query(
                """
                SELECT PaymentTransactionId, PaymentTransactionPaymentStatus, PaymentTransactionAmount
                FROM PaymentTransactions 
                WHERE PaymentTransactionSessionId = ?
                ORDER BY PaymentTransactionCreated DESC LIMIT 1
                """,
                (session_id,)
            )
            
            if not payment_transaction:
                logger.warning(f"No payment transaction found for session {session_id}")
                return False
            
            transaction_data = payment_transaction[0]
            payment_status = transaction_data["PaymentTransactionPaymentStatus"]
            payment_id = transaction_data["PaymentTransactionId"]
            payment_amount = transaction_data["PaymentTransactionAmount"]
            
            # Map payment transaction status to session payment status
            session_payment_status = PaymentSyncService._map_payment_status(payment_status)
            
            # Update session with payment information
            execute_update(
                """
                UPDATE ChargeSessions 
                SET ChargerSessionPaymentStatus = ?, ChargerSessionPaymentId = ?, ChargerSessionPaymentAmount = ?
                WHERE ChargeSessionId = ?
                """,
                (session_payment_status, payment_id, payment_amount, session_id)
            )
            
            logger.info(f"✅ Session {session_id} payment status synced to {session_payment_status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error syncing session payment status: {str(e)}")
            return False
    
    @staticmethod
    def _map_payment_status(payment_transaction_status):
        """
        Map payment transaction status to session payment status.
        
        Args:
            payment_transaction_status (str): Payment transaction status
            
        Returns:
            str: Mapped session payment status
        """
        status_mapping = {
            "pending": "pending",
            "succeeded": "paid",
            "failed": "failed",
            "canceled": "canceled",
            "refunded": "refunded"
        }
        
        return status_mapping.get(payment_transaction_status, "unknown")
    
    @staticmethod
    async def update_session_on_payment_completion(payment_transaction_id):
        """
        Update session when payment is completed.
        
        Args:
            payment_transaction_id (int): Payment transaction ID
            
        Returns:
            bool: True if successful
        """
        try:
            # Get payment transaction details
            payment_transaction = execute_query(
                """
                SELECT PaymentTransactionSessionId, PaymentTransactionPaymentStatus, PaymentTransactionAmount
                FROM PaymentTransactions 
                WHERE PaymentTransactionId = ?
                """,
                (payment_transaction_id,)
            )
            
            if not payment_transaction:
                logger.error(f"Payment transaction {payment_transaction_id} not found")
                return False
            
            transaction_data = payment_transaction[0]
            session_id = transaction_data["PaymentTransactionSessionId"]
            
            if not session_id:
                logger.warning(f"No session associated with payment transaction {payment_transaction_id}")
                return False
            
            # Sync the session status
            return await PaymentSyncService.sync_session_payment_status(session_id)
            
        except Exception as e:
            logger.error(f"❌ Error updating session on payment completion: {str(e)}")
            return False
    
    @staticmethod
    async def handle_payment_status_change(payment_transaction_id, new_payment_status):
        """
        Handle payment status change and sync to session.
        
        Args:
            payment_transaction_id (int): Payment transaction ID
            new_payment_status (str): New payment status
            
        Returns:
            bool: True if successful
        """
        try:
            # Update payment transaction status
            now = datetime.now().isoformat()
            execute_update(
                """
                UPDATE PaymentTransactions 
                SET PaymentTransactionPaymentStatus = ?, PaymentTransactionUpdated = ?
                WHERE PaymentTransactionId = ?
                """,
                (new_payment_status, now, payment_transaction_id)
            )
            
            # Sync to session
            success = await PaymentSyncService.update_session_on_payment_completion(payment_transaction_id)
            
            if success:
                logger.info(f"✅ Payment status updated to {new_payment_status} and synced to session")
            else:
                logger.error(f"❌ Failed to sync payment status to session")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error handling payment status change: {str(e)}")
            return False