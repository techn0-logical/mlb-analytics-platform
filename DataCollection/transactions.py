"""
Simple transactions and injuries collection
"""
from datetime import date, datetime, timezone
from sqlalchemy.orm import sessionmaker
from Database.config.database import DatabaseConfig
from Database.models.models import MLBTransaction, PlayerInjury
from .utils import normalize_team_name, make_api_request, log_result, log_error
import logging

logger = logging.getLogger(__name__)

def collect_transactions_for_date(target_date: date) -> tuple[int, int, int]:
    """
    Collect transactions for a single date
    Returns: (processed, inserted, updated)
    """
    db_config = DatabaseConfig()
    session = sessionmaker(bind=db_config.create_engine())()
    
    processed = inserted = updated = 0
    
    try:
        # Get transactions from MLB API
        url = "https://statsapi.mlb.com/api/v1/transactions"
        params = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'sportId': 1
        }
        
        response = make_api_request(url, params)
        data = response.json()
        
        if 'transactions' not in data:
            return processed, inserted, updated
        
        for transaction in data['transactions']:
            try:
                transaction_id = transaction.get('id')
                if not transaction_id:
                    continue
                
                # Check if transaction already exists
                existing = session.query(MLBTransaction).filter(
                    MLBTransaction.transaction_id == transaction_id
                ).first()
                
                if existing:
                    processed += 1
                    continue  # Skip duplicates
                
                # Parse transaction date
                date_str = transaction.get('date', '')
                try:
                    if 'T' in date_str:
                        transaction_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ').date()
                    else:
                        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue  # Skip if date parsing fails
                
                # Extract transaction details
                transaction_type = transaction.get('typeCode', '').lower()
                description = transaction.get('description', '')
                
                # Extract player and team info
                player_id = None
                from_team_id = None
                to_team_id = None
                
                if 'person' in transaction:
                    player_id = transaction['person'].get('id')
                
                # Skip transactions without a player_id (e.g. cash-only trades)
                # The DB requires player_id to be NOT NULL
                if player_id is None:
                    continue
                
                if 'fromTeam' in transaction:
                    from_team_name = transaction['fromTeam'].get('name', '')
                    from_team_id = normalize_team_name(from_team_name)
                
                if 'toTeam' in transaction:
                    to_team_name = transaction['toTeam'].get('name', '')
                    to_team_id = normalize_team_name(to_team_name)
                
                # Create new transaction
                new_transaction = MLBTransaction(
                    transaction_id=transaction_id,
                    transaction_date=transaction_date,
                    transaction_type=transaction_type,
                    description=description,
                    player_id=player_id,
                    from_team_id=from_team_id,
                    to_team_id=to_team_id,
                    season=transaction_date.year
                )
                
                session.add(new_transaction)
                processed += 1
                inserted += 1
                
            except Exception as e:
                session.rollback()
                log_error("Transactions", f"Error processing transaction {transaction.get('id', 'unknown')}: {e}")
                continue
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        log_error("Transactions", f"Failed to collect transactions for {target_date}: {e}")
    
    finally:
        session.close()
    
    return processed, inserted, updated

def collect_transactions(dates: list[date]) -> dict:
    """
    Collect transactions for multiple dates
    Returns summary dictionary
    """
    total_processed = total_inserted = total_updated = 0
    
    logger.info(f"🔄 Collecting transactions for {len(dates)} dates")
    
    for target_date in dates:
        processed, inserted, updated = collect_transactions_for_date(target_date)
        total_processed += processed
        total_inserted += inserted
        total_updated += updated
    
    log_result("Transactions", total_processed, total_inserted, total_updated)
    
    return {
        'source': 'transactions',
        'success': True,
        'processed': total_processed,
        'inserted': total_inserted,
        'updated': total_updated
    }