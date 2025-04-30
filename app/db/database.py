"""
Core database functionality for the OCPP server.
This module provides the basic database operations used throughout the application.
"""
import logging
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger("ocpp.db.core")

# Database connection string - this would be in a config file in a real application
DATABASE_PATH = "ocpp_database.db"

@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    
    Yields:
        sqlite3.Connection: An open database connection
    """
    connection = None
    try:
        connection = sqlite3.connect(DATABASE_PATH)
        # Enable dictionary access to rows
        connection.row_factory = sqlite3.Row
        yield connection
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE CONNECTION ERROR: {str(e)}")
        raise
    finally:
        if connection:
            connection.close()

def execute_query(query, params=()):
    """
    Execute a SELECT query and return the results.
    
    Args:
        query (str): SQL query to execute
        params (tuple): Parameters for the query
        
    Returns:
        list: List of rows as dictionaries, or empty list if query fails
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE QUERY ERROR: {str(e)}")
        logger.error(f"❌ FAILED QUERY: {query}")
        logger.error(f"❌ PARAMS: {params}")
        return []

def execute_update(query, params=()):
    """
    Execute an UPDATE query.
    
    Args:
        query (str): SQL query to execute
        params (tuple): Parameters for the query
        
    Returns:
        int: Number of rows affected, or -1 if update fails
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE UPDATE ERROR: {str(e)}")
        logger.error(f"❌ FAILED QUERY: {query}")
        logger.error(f"❌ PARAMS: {params}")
        return -1

def execute_insert(query, params=()):
    """
    Execute an INSERT query.
    
    Args:
        query (str): SQL query to execute
        params (tuple): Parameters for the query
        
    Returns:
        int: Last inserted row ID, or -1 if insert fails
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE INSERT ERROR: {str(e)}")
        logger.error(f"❌ FAILED QUERY: {query}")
        logger.error(f"❌ PARAMS: {params}")
        return -1

def execute_delete(query, params=()):
    """
    Execute a DELETE query.
    
    Args:
        query (str): SQL query to execute
        params (tuple): Parameters for the query
        
    Returns:
        int: Number of rows affected, or -1 if delete fails
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE DELETE ERROR: {str(e)}")
        logger.error(f"❌ FAILED QUERY: {query}")
        logger.error(f"❌ PARAMS: {params}")
        return -1

def execute_transaction(queries_and_params):
    """
    Execute multiple queries in a single transaction.
    
    Args:
        queries_and_params (list): List of (query, params) tuples
        
    Returns:
        bool: True if transaction was successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for query, params in queries_and_params:
                cursor.execute(query, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"❌ DATABASE TRANSACTION ERROR: {str(e)}")
        # Log the failed transaction
        for i, (query, params) in enumerate(queries_and_params):
            logger.error(f"❌ TRANSACTION QUERY {i}: {query}")
            logger.error(f"❌ TRANSACTION PARAMS {i}: {params}")
        return False

def init_db():
    """
    Initialize the database with schema if needed.
    This would read from a schema file in a real application.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # This is a placeholder. In a real app, you would read the schema from a file.
        # For example, from the ocpp_db.sql file
        with open("ocpp_db.sql", "r") as schema_file:
            schema = schema_file.read()
            
        with get_db_connection() as conn:
            conn.executescript(schema)
            return True
    except (sqlite3.Error, IOError) as e:
        logger.error(f"❌ DATABASE INITIALIZATION ERROR: {str(e)}")
        return False