"""
Asset classification groups used across the application.
This is the single source of truth for asset groupings.
"""

# Asset groups for portfolio classification
ASSET_GROUPS = {
    'BTC': ['BTC', 'TBTC', 'WBTC'],  # Bitcoin et dérivés (BCH removed - it's different)
    'ETH': ['ETH', 'WETH', 'STETH', 'WSTETH', 'RETH', 'CBETH'],  # Ethereum et liquid staking
    'Stablecoins': ['USDT', 'USDC', 'USD', 'DAI', 'BUSD', 'TUSD', 'FDUSD', 'PAXG', 'USTC'],  # Stablecoins et gold
    'SOL': ['SOL', 'SOL2', 'JUPSOL', 'JITOSOL'],  # Solana écosystème
    'L1/L0 majors': [
        # Layer 1 blockchains majors
        'ATOM', 'ATOM2', 'DOT', 'DOT2', 'ADA', 'AVAX', 'NEAR', 'XRP', 'LINK', 'BNB', 
        'LTC', 'XLM', 'EGLD3', 'XTZ', 'VET', 'SUI3', 'INJ2', 'TRX', 'CRO', 'ERA'
    ],
    'L2/Scaling': ['OP', 'ARB', 'LRC', 'MATIC', 'POL'],  # Layer 2 et scaling
    'DeFi': [
        # DeFi tokens
        'UNI', 'UNI2', 'SUSHI', 'AAVE', 'COMP', 'CAKE', 'CFG'
    ],
    'AI/Data': ['FET', 'OCEAN', 'GRT', 'RENDER', 'TAO6'],  # AI et Data
    'Privacy': ['XMR'],  # Privacy coins
    'Memecoins': ['DOGE', 'PENGU7'],  # Meme tokens
    'Gaming/NFT': ['S5'],  # Gaming et NFTs  
    'Exchange Tokens': ['BGB', 'BNB', 'CHSB'],  # Exchange tokens
    'Others': [
        # Tous les autres assets non classifiés
        'IMO', 'VVV3', 'OXT', 'BAT', 'YFII', 'ANC2', 'BCH'  # BCH moved to Others
    ]
}

def get_asset_group(symbol: str) -> str:
    """
    Get the group name for a given asset symbol.
    
    Args:
        symbol: Asset symbol (e.g., 'BTC', 'ETH')
        
    Returns:
        Group name or 'Others' if not found
    """
    symbol_upper = symbol.upper()
    
    for group_name, symbols in ASSET_GROUPS.items():
        if symbol_upper in symbols:
            return group_name
    
    return 'Others'

def get_group_symbols(group_name: str) -> list:
    """
    Get all symbols for a given group.
    
    Args:
        group_name: Name of the group
        
    Returns:
        List of symbols in the group
    """
    return ASSET_GROUPS.get(group_name, [])

def get_all_groups() -> list:
    """Get list of all available groups."""
    return list(ASSET_GROUPS.keys())

# Portfolio color scheme for charts
PORTFOLIO_COLORS = [
    '#3b82f6',  # Blue
    '#ef4444',  # Red
    '#10b981',  # Green
    '#f59e0b',  # Yellow
    '#8b5cf6',  # Purple
    '#06b6d4',  # Cyan
    '#84cc16',  # Lime
    '#f97316',  # Orange
    '#ec4899',  # Pink
    '#6366f1'   # Indigo
]

# Exchange priority mapping
EXCHANGE_PRIORITY = {
    'binance': 1,
    'kraken': 2,
    'coinbase': 3,
    'metamask': 4,
    'ledger': 5,
    'unknown': 999
}