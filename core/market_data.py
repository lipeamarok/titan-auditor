import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional

class MarketDataService:
    """
    Serviço responsável por buscar dados de mercado em tempo real (B3/Yahoo Finance).
    Transforma o Titan de um 'leitor de PDF' em um 'Terminal de Mercado'.
    """

    @staticmethod
    def get_ticker_info(ticker: str, region: str = "BR") -> Optional[Dict[str, Any]]:
        """
        Busca dados globais.
        region: 'BR' (adiciona .SA), 'US' (sem sufixo), 'CRYPTO' (adiciona -USD)
        """

        # 1. Tratamento Inteligente de Sufixo
        ticker = ticker.upper().strip()

        if region == "BR" and not ticker.endswith(".SA"):
            search_ticker = f"{ticker}.SA"
        elif region == "CRYPTO" and not ticker.endswith("-USD"):
            search_ticker = f"{ticker}-USD"
        else:
            # EUA e outros mercados geralmente não precisam de sufixo ou o usuário já digita
            search_ticker = ticker

        try:
            stock = yf.Ticker(search_ticker)
            info = stock.info

            # Estratégia de Fallback para Preço (Cripto e ETFs as vezes falham no 'currentPrice')
            price = info.get('currentPrice')
            if price is None:
                price = info.get('regularMarketPrice')
            if price is None:
                # Tenta fast_info (mais robusto para realtime)
                try:
                    price = stock.fast_info.last_price
                except:
                    pass

            # Se ainda assim não tiver preço, aborta
            if price is None:
                return None

            # Ajustes específicos para Cripto
            if region == "CRYPTO":
                sector = "Criptoativo"
                industry = "Blockchain / Digital Assets"
                currency = "USD"
            else:
                sector = info.get('sector', 'ETF/Indefinido')
                industry = info.get('industry', 'Fund/Other')
                currency = info.get('currency', 'BRL')

            return {
                "name": info.get('longName', info.get('shortName', search_ticker)), # Fallback para shortName
                "sector": sector,
                "industry": industry,
                "price": price,
                "currency": currency,
                "market_cap": info.get('marketCap', 0),
                "pe_ratio": info.get('trailingPE', 0.0),
                "dividend_yield": info.get('dividendYield', 0.0),
                "volume": info.get('volume', info.get('regularMarketVolume', 0)), # Volume 24h
                "high_24h": info.get('dayHigh', info.get('regularMarketDayHigh', 0.0)),
                "low_24h": info.get('dayLow', info.get('regularMarketDayLow', 0.0)),
                "logo_url": info.get('logo_url', ''),
                "summary": info.get('longBusinessSummary', info.get('description', "Descrição indisponível.")),
                "website": info.get('website', '#'),
                "is_etf": info.get('quoteType', '') == 'ETF'
            }
        except Exception as e:
            print(f"Erro ao buscar {search_ticker}: {e}")
            return None

    @staticmethod
    def get_price_history(ticker: str, region: str = "BR", period="1y") -> pd.DataFrame:
        # Mesma lógica de sufixo aqui
        ticker = ticker.upper().strip()
        if region == "BR" and not ticker.endswith(".SA"):
            ticker = f"{ticker}.SA"
        elif region == "CRYPTO" and not ticker.endswith("-USD"):
            ticker = f"{ticker}-USD"

        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        return hist[['Close']]
