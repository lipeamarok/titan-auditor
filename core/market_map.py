# core/market_map.py

# Dicionário de Tickers Especiais (Commodities e Índices têm códigos estranhos no Yahoo)
MACRO_ASSETS = {
    "indices": {
        "🇧🇷 Ibovespa": "^BVSP",
        "🇺🇸 S&P 500": "^GSPC",
        "🇺🇸 Nasdaq 100": "^NDX",
        "🇺🇸 Dow Jones": "^DJI",
        "🇪🇺 Euro Stoxx 50": "^STOXX50E"
    },
    "currencies": {
        "🇺🇸 Dólar (USD/BRL)": "BRL=X", # Quanto vale 1 USD em Reais
        "🇪🇺 Euro (EUR/BRL)": "EURBRL=X",
        "🇬🇧 Libra (GBP/BRL)": "GBPBRL=X",
        "Euro/Dólar": "EURUSD=X"
    },
    "commodities": {
        "Petróleo Brent": "BZ=F",
        "Petróleo WTI": "CL=F",
        "Ouro": "GC=F",
        "Prata": "SI=F",
        "Milho": "ZC=F",
        "Café": "KC=F"
    }
}

# Sugestões de Busca (Top of Mind) para o usuário não começar do zero
POPULAR_TICKERS = {
    "BR_STOCK": ["PETR4", "VALE3", "ITUB4", "WEGE3", "BBAS3", "MGLU3"],
    "US_STOCK": ["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META", "GOOGL"],
    "CRYPTO": ["BTC", "ETH", "SOL", "DOGE", "BNB"],
    "FII": ["HGLG11", "KNIP11", "MXRF11", "VISC11", "XPML11"],
    "GLOBAL_ETF": ["IVV", "QQQ", "EWZ", "SMH", "VNQ"]
}
