"""
Data formatting utilities
"""
from typing import List, Dict, Any
import csv
import io

def to_csv(actions: List[Dict[str, Any]]) -> str:
    """Convert list of actions to CSV string"""
    if not actions:
        return ""
    
    output = io.StringIO()
    
    # Define column order
    fieldnames = [
        'symbol', 'action', 'amount', 'value_usd', 'location', 
        'current_allocation', 'target_allocation', 'drift',
        'priority', 'notes'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for action in actions:
        # Ensure all required fields exist
        row = {field: action.get(field, '') for field in fieldnames}
        writer.writerow(row)
    
    return output.getvalue()

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string"""
    if currency.upper() == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format value as percentage string"""
    return f"{value:.{decimals}f}%"

def format_action_summary(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a summary of rebalancing actions"""
    if not actions:
        return {
            "total_actions": 0,
            "total_value": 0,
            "buy_actions": 0,
            "sell_actions": 0,
            "summary": "No actions required"
        }
    
    buy_actions = [a for a in actions if a.get('action') == 'buy']
    sell_actions = [a for a in actions if a.get('action') == 'sell']
    
    total_value = sum(float(a.get('value_usd', 0)) for a in actions)
    
    return {
        "total_actions": len(actions),
        "total_value": total_value,
        "buy_actions": len(buy_actions),
        "sell_actions": len(sell_actions),
        "total_value_formatted": format_currency(total_value),
        "summary": f"{len(actions)} actions totaling {format_currency(total_value)}"
    }