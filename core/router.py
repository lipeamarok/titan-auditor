# core/router.py
"""
Titan Router - Central de Inteligência para Roteamento de Fontes de Dados

Este módulo decide automaticamente onde buscar dados baseado no tipo de ativo:
- BR_STOCK: CVM (Dados Abertos)
- US_STOCK: SEC EDGAR
- CRYPTO: CoinGecko API
- ETF: yfinance (Holdings/Fees)
"""

import os
import yfinance as yf
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json


class AssetType(Enum):
    """Tipos de ativos suportados pelo Titan."""
    BR_STOCK = "BR_STOCK"
    US_STOCK = "US_STOCK"
    CRYPTO = "CRYPTO"
    BR_FII = "BR_FII"
    US_ETF = "US_ETF"
    BR_ETF = "BR_ETF"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    UNKNOWN = "UNKNOWN"


@dataclass
class DocumentResult:
    """Resultado da busca de documento."""
    success: bool
    asset_type: AssetType
    document_url: Optional[str] = None
    document_content: Optional[bytes] = None
    document_type: Optional[str] = None  # PDF, HTML, JSON
    fallback_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TitanRouter:
    """
    Central de Inteligência que decide onde buscar o dado baseado no Ticker.
    Implementa o padrão "Busca Ativa, Falha Graciosa".
    """

    # User-Agent para APIs (SEC exige identificação)
    USER_AGENT = "TitanAuditor/1.0 (lipearouck@gmail.com)"

    # Headers padrão para requests
    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    def __init__(self):
        # Cache de índice CVM (evita re-download)
        self._cvm_index_cache = None
        self._cvm_index_date = None

    def identify_asset(self, ticker: str, region: str | None = None) -> AssetType:
        """
        Identifica a natureza do ativo baseado no ticker e região.

        Args:
            ticker: Código do ativo (ex: PETR4, AAPL, BTC-USD)
            region: Região opcional (BR, US, CRYPTO)

        Returns:
            AssetType enum
        """
        ticker = ticker.upper().strip()

        # Prioriza região se fornecida
        if region:
            region = region.upper()
            if region == "BR":
                if ticker.endswith("11"):  # FIIs terminam em 11
                    return AssetType.BR_FII
                return AssetType.BR_STOCK
            elif region == "CRYPTO":
                return AssetType.CRYPTO
            elif region == "US":
                # Verifica se é ETF via Yahoo
                return self._check_us_asset_type(ticker)

        # Detecção automática por padrão de ticker
        if ticker.endswith(".SA"):
            clean = ticker.replace(".SA", "")
            if clean.endswith("11"):
                return AssetType.BR_FII
            return AssetType.BR_STOCK

        if "-USD" in ticker or ticker in ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB"]:
            return AssetType.CRYPTO

        if ticker.startswith("^"):
            return AssetType.INDEX

        if "=F" in ticker:
            return AssetType.COMMODITY

        if "=X" in ticker:
            return AssetType.CURRENCY

        # Default: tenta identificar via Yahoo
        return self._check_us_asset_type(ticker)

    def _check_us_asset_type(self, ticker: str) -> AssetType:
        """Verifica no Yahoo se é Stock ou ETF."""
        try:
            info = yf.Ticker(ticker).info
            quote_type = info.get('quoteType', '')
            if quote_type == 'ETF':
                return AssetType.US_ETF
            return AssetType.US_STOCK
        except Exception:
            return AssetType.US_STOCK  # Default para stock

    def fetch_audit_data(self, ticker: str, region: str | None = None) -> DocumentResult:
        """
        Método principal: busca dados para auditoria baseado no tipo de ativo.

        Implementa "Busca Ativa, Falha Graciosa":
        1. Identifica o tipo de ativo
        2. Tenta buscar documento oficial automaticamente
        3. Se falhar, retorna mensagem amigável para upload manual
        """
        asset_type = self.identify_asset(ticker, region)

        # Roteamento por tipo de ativo
        if asset_type == AssetType.BR_STOCK:
            return self._fetch_cvm_document(ticker)

        elif asset_type == AssetType.BR_FII:
            return self._fetch_cvm_document(ticker, doc_type="FII")

        elif asset_type == AssetType.US_STOCK:
            return self._fetch_sec_document(ticker)

        elif asset_type == AssetType.US_ETF:
            return self._fetch_etf_data(ticker)

        elif asset_type == AssetType.CRYPTO:
            return self._fetch_crypto_data(ticker)

        else:
            return DocumentResult(
                success=False,
                asset_type=asset_type,
                fallback_message=f"Tipo de ativo '{asset_type.value}' não suporta auditoria automática."
            )

    # =========================================================================
    # MÓDULO BRASIL (CVM) - Dados Estruturados
    # =========================================================================

    # Tickers de Instituições Financeiras (Bancos) - usam plano de contas COSIF
    # Estes tickers têm estrutura contábil diferente de empresas corporativas
    BANKING_TICKERS = {
        "ITUB4", "ITUB3",  # Itaú Unibanco
        "BBDC4", "BBDC3",  # Bradesco
        "BBAS3",           # Banco do Brasil
        "SANB11", "SANB3", "SANB4",  # Santander
        "BPAC11", "BPAC3", "BPAC5",  # BTG Pactual
        "BBSE3",           # BB Seguridade (holding bancária)
        "BRSR6", "BRSR3",  # Banrisul
        "ABCB4",           # ABC Brasil
        "BMGB4",           # BMG
        "BIDI11", "BIDI4", # Inter (banco digital)
        "BPAN4",           # Banco Pan
        "PINE4",           # Pine
        "CIEL3",           # Cielo (adquirente, usa métricas bancárias)
    }

    # Mapeamento de tickers para nome da empresa na CVM
    # A CVM usa DENOM_CIA (nome completo), não ticker de pregão
    TICKER_TO_COMPANY = {
        "MGLU3": "MAGAZINE LUIZA",
        "PETR4": "PETROLEO BRASILEIRO",
        "PETR3": "PETROLEO BRASILEIRO",
        "VALE3": "VALE",
        "ITUB4": "ITAU UNIBANCO",
        "BBDC4": "BRADESCO",
        "BBAS3": "BCO BRASIL",
        "WEGE3": "WEG",
        "ABEV3": "AMBEV",
        "RENT3": "LOCALIZA",
        "LREN3": "LOJAS RENNER",
        "RADL3": "RAIA DROGASIL",
        "SUZB3": "SUZANO",
        "JBSS3": "JBS",
        "GGBR4": "GERDAU",
        "CSNA3": "SID NACIONAL",
        "EMBR3": "EMBRAER",
        "AZUL4": "AZUL",
        "COGN3": "COGNA",
        "VVAR3": "VIA",
        "VIIA3": "VIA",
        "B3SA3": "B3",
        "CIEL3": "CIELO",
        "TOTS3": "TOTVS",
        "PRIO3": "PETRORIO",
        "RAIZ4": "RAIZEN",
    }

    def _fetch_cvm_document(self, ticker: str, doc_type: str = "ITR") -> DocumentResult:
        """
        Busca dados financeiros estruturados no Portal de Dados Abertos da CVM.

        A CVM disponibiliza arquivos ZIP com CSVs estruturados contendo:
        - BPA: Balanço Patrimonial Ativo
        - BPP: Balanço Patrimonial Passivo
        - DRE: Demonstração do Resultado

        Endpoint: http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/
        """
        import io
        import zipfile
        import csv

        ticker_clean = ticker.upper().replace(".SA", "")

        try:
            # 1. Determina o nome da empresa para buscar na CVM
            company_name = self.TICKER_TO_COMPANY.get(ticker_clean)

            if not company_name:
                # Tenta buscar pelo ticker no índice de empresas
                company_name = self._find_company_in_cvm(ticker_clean)

            if not company_name:
                return self._cvm_fallback(ticker_clean, "Empresa não encontrada no mapeamento")

            # 2. Baixa o ZIP do ano mais recente
            year = datetime.now().year
            zip_url = f"http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"

            response = requests.get(zip_url, headers=self.HEADERS, timeout=60)

            if response.status_code != 200:
                # Tenta ano anterior
                year -= 1
                zip_url = f"http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
                response = requests.get(zip_url, headers=self.HEADERS, timeout=60)

            if response.status_code != 200:
                return self._cvm_fallback(ticker_clean, f"ZIP não disponível: HTTP {response.status_code}")

            # 3. Detecta se é banco/IF para usar mapeamento correto
            is_banking = ticker_clean in self.BANKING_TICKERS

            # 4. Extrai dados estruturados do ZIP
            xbrl_data = self._extract_cvm_data(response.content, company_name, year, is_banking=is_banking)

            if xbrl_data:
                metadata = xbrl_data.pop("_metadata", {})
                fiscal_months = metadata.get("fiscal_months", 12)
                is_ytd = metadata.get("is_ytd", False)
                detected_sector = metadata.get("sector", "Corporate")

                # Form type mais descritivo
                if fiscal_months == 3:
                    form_type_desc = "ITR 1T (3 meses)"
                elif fiscal_months == 6:
                    form_type_desc = "ITR 2T (6 meses)"
                elif fiscal_months == 9:
                    form_type_desc = "ITR 3T (9 meses)"
                else:
                    form_type_desc = "DFP (12 meses)"

                return DocumentResult(
                    success=True,
                    asset_type=AssetType.BR_STOCK,
                    document_type="XBRL",  # Mesmo tipo que SEC para reusar o fluxo
                    metadata={
                        "source": "CVM Dados Abertos",
                        "sector": detected_sector,  # Banking ou Corporate
                        "form_type": form_type_desc,
                        "filing_date": metadata.get("period"),
                        "ticker": ticker_clean,
                        "company": company_name,
                        "fiscal_months": fiscal_months,
                        "is_ytd": is_ytd,
                        "xbrl_data": xbrl_data  # Dados financeiros já extraídos!
                    }
                )

            return self._cvm_fallback(ticker_clean, "Dados não encontrados no ZIP")

        except Exception as e:
            return self._cvm_fallback(ticker_clean, str(e))

    def _find_company_in_cvm(self, ticker: str) -> str | None:
        """
        Busca o nome da empresa no índice da CVM pelo ticker ou parte do nome.
        """
        import io
        import zipfile
        import csv

        try:
            year = datetime.now().year
            zip_url = f"http://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
            response = requests.get(zip_url, headers=self.HEADERS, timeout=60)

            if response.status_code != 200:
                return None

            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                with zf.open(f'itr_cia_aberta_{year}.csv') as f:
                    text_file = io.TextIOWrapper(f, encoding='latin-1')
                    reader = csv.DictReader(text_file, delimiter=';')

                    # Remove número do ticker (ex: MGLU3 -> MGLU)
                    ticker_base = ''.join(c for c in ticker if not c.isdigit())

                    for row in reader:
                        denom = row.get('DENOM_CIA', '').upper()
                        # Busca por correspondência parcial
                        if ticker_base in denom or ticker in denom:
                            return denom

            return None
        except Exception:
            return None

    def _extract_cvm_data(self, zip_content: bytes, company_name: str, year: int, is_banking: bool = False) -> dict | None:
        """
        Extrai dados financeiros estruturados do ZIP da CVM.

        Para empresas CORPORATIVAS (is_banking=False):
        - 1 = Ativo Total
        - 1.01 = Ativo Circulante
        - 2.01 = Passivo Circulante
        - 2.02 = Passivo Não Circulante
        - 2.03 = Patrimônio Líquido
        - 3.01 = Receita
        - 3.05 = EBIT
        - 3.09 = Lucro Líquido

        Para BANCOS/IFs (is_banking=True):
        Estrutura diferente - bancos não têm "circulante/não-circulante" tradicional
        - 1 = Ativo Total
        - 2 = Passivo Total
        - 2.03 ou 2.07 = Patrimônio Líquido
        - 3.01 = Receitas da Intermediação Financeira
        - 3.11 = Lucro Líquido
        Obs: Bancos usam métricas específicas (ROE bancário, Basileia, etc.)
        """
        import io
        import zipfile
        import csv

        def extract_data(zf, filename):
            """Extrai dados de um CSV do ZIP filtrando por empresa."""
            data = {}
            try:
                with zf.open(filename) as f:
                    text_file = io.TextIOWrapper(f, encoding='latin-1')
                    reader = csv.DictReader(text_file, delimiter=';')
                    for row in reader:
                        denom = row.get('DENOM_CIA', '').upper()
                        if company_name.upper() in denom:
                            dt_ref = row.get('DT_REFER', '')
                            conta = row.get('CD_CONTA', '')
                            valor_str = row.get('VL_CONTA', '0')
                            try:
                                valor = float(valor_str) if valor_str else 0
                            except ValueError:
                                valor = 0
                            key = (dt_ref, conta)
                            data[key] = valor
            except Exception:
                pass
            return data

        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                # Extrai dados de cada demonstrativo
                bpa = extract_data(zf, f'itr_cia_aberta_BPA_con_{year}.csv')  # Balanço Ativo
                bpp = extract_data(zf, f'itr_cia_aberta_BPP_con_{year}.csv')  # Balanço Passivo
                dre = extract_data(zf, f'itr_cia_aberta_DRE_con_{year}.csv')  # DRE

                if not bpa and not bpp:
                    return None

                # Encontra a data mais recente disponível
                all_dates = set()
                for key in list(bpa.keys()) + list(bpp.keys()) + list(dre.keys()):
                    all_dates.add(key[0])

                if not all_dates:
                    return None

                latest = max(all_dates)

                # Escala: CVM usa valores em milhares de reais
                ESCALA = 1000

                # Mapeamento de contas CVM para nosso schema
                extracted = {}

                if is_banking:
                    # =========================================================
                    # EXTRAÇÃO PARA BANCOS / INSTITUIÇÕES FINANCEIRAS
                    # =========================================================
                    # Bancos IFRS usam estrutura diferente:
                    # - 2.08 = Patrimônio Líquido (não 2.03!)
                    # - 2.03 = Passivos Financeiros ao Custo Amortizado
                    # - Não têm circulante/não-circulante tradicional
                    
                    extracted["total_assets"] = bpa.get((latest, '1'), 0) * ESCALA
                    
                    # PL de bancos IFRS: está em 2.08 (não 2.03!)
                    # 2.03 em bancos IFRS = "Passivos Financeiros ao Custo Amortizado"
                    equity = bpp.get((latest, '2.08'), 0)
                    if equity == 0:
                        # Fallback para estrutura não-IFRS
                        equity = bpp.get((latest, '2.07'), 0)
                    if equity == 0:
                        # Último recurso
                        equity = bpp.get((latest, '2.03'), 0)
                    extracted["equity"] = equity * ESCALA
                    
                    # Passivo Total = Total do Passivo (2) menos PL
                    total_passivo_e_pl = bpp.get((latest, '2'), 0) * ESCALA
                    extracted["total_liabilities"] = total_passivo_e_pl - extracted["equity"]
                    
                    # Bancos IFRS não têm circulante tradicional
                    # Usamos proxies ou deixamos nulo para evitar alertas falsos
                    extracted["current_assets"] = None  # Não aplicável a bancos
                    extracted["current_liabilities"] = None  # Não aplicável a bancos
                    
                    # Caixa: Disponibilidades (1.01.01) ou similar
                    cash = bpa.get((latest, '1.01.01'), 0)
                    if cash == 0:
                        cash = bpa.get((latest, '1.01.01.01'), 0)
                    if cash == 0:
                        # Para bancos IFRS, tentar 1.01 (Caixa e Saldos em Bancos Centrais)
                        cash = bpa.get((latest, '1.01'), 0)
                    extracted["cash"] = cash * ESCALA
                    
                    # DRE Bancária IFRS
                    # 3.01 = Receita de Juros (ou Margem Financeira)
                    extracted["revenue"] = dre.get((latest, '3.01'), 0) * ESCALA
                    
                    # EBIT para bancos = Resultado antes de IR
                    ebit = dre.get((latest, '3.05'), 0)
                    if ebit == 0:
                        ebit = dre.get((latest, '3.07'), 0)
                    extracted["ebit"] = ebit * ESCALA
                    
                    # Lucro Líquido
                    net_income = dre.get((latest, '3.11'), 0)
                    if net_income == 0:
                        net_income = dre.get((latest, '3.09'), 0)
                    extracted["net_income"] = net_income * ESCALA
                    
                    # Lucros Acumulados - buscar nas subcontas do PL (2.08.x)
                    retained = bpp.get((latest, '2.08.05'), 0) + bpp.get((latest, '2.08.04'), 0)
                    if retained == 0:
                        retained = bpp.get((latest, '2.08.03'), 0)  # Reservas
                    if retained == 0:
                        # Fallback para estrutura tradicional
                        retained = bpp.get((latest, '2.03.05'), 0) + bpp.get((latest, '2.03.04'), 0)
                    extracted["retained_earnings"] = retained * ESCALA
                    
                    # Dívida de Longo Prazo (não se aplica da mesma forma a bancos)
                    extracted["long_term_debt"] = 0
                    
                    # Gross profit para bancos = Resultado Bruto da Intermediação
                    extracted["gross_profit"] = dre.get((latest, '3.03'), 0) * ESCALA
                    
                    # Depósitos (importante para bancos)
                    deposits = bpp.get((latest, '2.01.02'), 0)  # Depósitos
                    extracted["deposits"] = deposits * ESCALA
                    
                    # =========================================================
                    # MÉTRICAS DE CRÉDITO (PDD / Inadimplência)
                    # =========================================================
                    # Carteira de Crédito (1.02.03.05 = Operações de Crédito)
                    loan_portfolio = bpa.get((latest, '1.02.03.05'), 0) * ESCALA
                    if loan_portfolio == 0:
                        # Fallback: tentar 1.02.01.01 ou somar operações de crédito
                        loan_portfolio = bpa.get((latest, '1.02.01.01'), 0) * ESCALA
                    extracted["loan_portfolio"] = loan_portfolio
                    
                    # PDD - Provisão para Perda Esperada (1.02.03.07) - valor negativo no balanço
                    pdd_balance = abs(bpa.get((latest, '1.02.03.07'), 0)) * ESCALA
                    
                    # PDD na DRE (3.02.02) - Despesa de provisão do período
                    pdd_expense = abs(dre.get((latest, '3.02.02'), 0)) * ESCALA
                    
                    # Calcular NPL (Non-Performing Loans) como proxy
                    # NPL = PDD Acumulada / Carteira de Crédito
                    # Isso é uma aproximação - quanto maior a provisão, maior a inadimplência esperada
                    if loan_portfolio > 0 and pdd_balance > 0:
                        npl_proxy = pdd_balance / loan_portfolio
                        extracted["non_performing_loans"] = npl_proxy
                    else:
                        extracted["non_performing_loans"] = None
                    
                    # Guardar PDD para contexto
                    extracted["pdd_balance"] = pdd_balance
                    extracted["pdd_expense"] = pdd_expense
                    
                else:
                    # =========================================================
                    # EXTRAÇÃO PARA EMPRESAS CORPORATIVAS (não-financeiras)
                    # =========================================================
                    
                    # BALANÇO PATRIMONIAL (BPA/BPP)
                    extracted["total_assets"] = bpa.get((latest, '1'), 0) * ESCALA
                    extracted["current_assets"] = bpa.get((latest, '1.01'), 0) * ESCALA
                    extracted["current_liabilities"] = bpp.get((latest, '2.01'), 0) * ESCALA
                    extracted["equity"] = bpp.get((latest, '2.03'), 0) * ESCALA

                    # Passivo não circulante
                    non_current_liab = bpp.get((latest, '2.02'), 0) * ESCALA
                    extracted["total_liabilities"] = extracted["current_liabilities"] + non_current_liab

                    # Lucros Acumulados (2.03.04 = Reservas de Lucros + 2.03.05 = Lucros/Prejuízos Acumulados)
                    retained_earnings = bpp.get((latest, '2.03.04'), 0) + bpp.get((latest, '2.03.05'), 0)
                    extracted["retained_earnings"] = retained_earnings * ESCALA

                    # Caixa (1.01.01 = Caixa e Equivalentes)
                    extracted["cash"] = bpa.get((latest, '1.01.01'), 0) * ESCALA

                    # Dívida de Longo Prazo (2.02.01 = Empréstimos e Financiamentos LP)
                    extracted["long_term_debt"] = bpp.get((latest, '2.02.01'), 0) * ESCALA

                    # DRE (valores YTD - já vem acumulado no ITR)
                    extracted["revenue"] = dre.get((latest, '3.01'), 0) * ESCALA
                    extracted["ebit"] = dre.get((latest, '3.05'), 0) * ESCALA
                    extracted["net_income"] = dre.get((latest, '3.09'), 0) * ESCALA

                    # Lucro Bruto (para margem bruta real)
                    extracted["gross_profit"] = dre.get((latest, '3.03'), 0) * ESCALA

                # Verifica dados mínimos
                if not extracted.get("total_assets") or not extracted.get("equity"):
                    return None

                # Determina quantos meses o período YTD cobre
                # latest = "2025-09-30" -> mês 9 -> Q3 -> 9 meses YTD
                period_month = int(latest.split('-')[1])
                fiscal_months = period_month  # Jan=1, Mar=3, Jun=6, Set=9, Dez=12

                # Metadata
                extracted["_metadata"] = {
                    "source": "CVM Dados Abertos",
                    "period": latest,
                    "form_type": "ITR",
                    "company": company_name,
                    "extraction_method": "Structured CSV from ZIP",
                    "scale": "Values in BRL",
                    "sector": "Banking" if is_banking else "Corporate",  # IMPORTANTE!
                    "fiscal_months": fiscal_months,  # Quantos meses o YTD cobre
                    "is_ytd": fiscal_months < 12  # True se não é ano completo
                }

                return extracted

        except Exception:
            return None

    def _cvm_fallback(self, ticker: str, error: str | None = None) -> DocumentResult:
        """Fallback quando não conseguimos buscar automaticamente na CVM."""

        rad_url = "https://www.rad.cvm.gov.br/ENET/frmGerenciaPaginaFRE.aspx"

        msg = f"""
Não foi possível localizar automaticamente o ITR de {ticker} na CVM.

**Erro:** {error if error else 'Desconhecido'}

**Busca Manual:**
1. Acesse o [Portal RAD da CVM]({rad_url})
2. Busque por "{ticker}"
3. Baixe o ITR (Informações Trimestrais) mais recente
4. Faça upload do PDF abaixo

**Dica:** Se o ticker não está no mapeamento, adicione-o em `TICKER_TO_COMPANY` no arquivo `router.py`
        """

        return DocumentResult(
            success=False,
            asset_type=AssetType.BR_STOCK,
            fallback_message=msg.strip(),
            metadata={"manual_search_url": rad_url, "error": error}
        )

    # =========================================================================
    # MÓDULO EUA (SEC EDGAR)
    # =========================================================================

    def _fetch_sec_xbrl_data(self, cik: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados financeiros estruturados via API XBRL da SEC.

        Esta é a forma mais confiável de obter dados financeiros da SEC.
        Retorna dados padronizados em JSON, sem necessidade de parsing HTML.

        IMPORTANTE:
        - Campos de BALANÇO (Assets, Equity): point-in-time, pega o mais recente
        - Campos de DRE (Net Income, Revenue): período, pega YTD do trimestre atual

        API: https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json
        """
        base_url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap"

        # Mapeamento de conceitos XBRL para nosso schema
        # Separamos por tipo: balance_sheet (point-in-time) vs income_statement (período)
        balance_sheet_concepts = {
            "Assets": "total_assets",
            "AssetsCurrent": "current_assets",
            "Liabilities": "total_liabilities",
            "LiabilitiesCurrent": "current_liabilities",
            "StockholdersEquity": "equity",
            "RetainedEarningsAccumulatedDeficit": "retained_earnings",
            "CashAndCashEquivalentsAtCarryingValue": "cash",
            "LongTermDebt": "long_term_debt",
            "ShortTermBorrowings": "short_term_debt",
        }

        income_statement_concepts = {
            "NetIncomeLoss": "net_income",
            "Revenues": "revenue",
            "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue_alt",
            "OperatingIncomeLoss": "ebit",
            "InterestExpense": "interest_expense",
        }

        extracted_data = {}
        latest_period = None
        form_type = None

        # === BALANCE SHEET: Pega o valor mais recente (point-in-time) ===
        for concept, field_name in balance_sheet_concepts.items():
            try:
                url = f"{base_url}/{concept}.json"
                response = requests.get(url, headers=self.HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    units = data.get("units", {})
                    usd_values = units.get("USD", [])

                    if usd_values:
                        # Filtra apenas 10-Q e 10-K
                        quarterly = [v for v in usd_values if v.get("form") in ("10-Q", "10-K")]
                        if quarterly:
                            # Ordena por data mais recente
                            sorted_values = sorted(
                                quarterly,
                                key=lambda x: x.get("end", ""),
                                reverse=True
                            )
                            latest = sorted_values[0]
                            extracted_data[field_name] = latest.get("val", 0)

                            # Captura metadata do período (apenas uma vez)
                            if latest_period is None:
                                latest_period = latest.get("end")
                                form_type = latest.get("form", "10-Q")

            except Exception:
                continue

        # === INCOME STATEMENT: Pega YTD do trimestre atual ===
        # Para Q3, queremos o período de 9 meses (Jan-Set), não TTM (12 meses)
        for concept, field_name in income_statement_concepts.items():
            try:
                url = f"{base_url}/{concept}.json"
                response = requests.get(url, headers=self.HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    units = data.get("units", {})
                    usd_values = units.get("USD", [])

                    if usd_values and latest_period:
                        # Extrai o ano do período mais recente
                        year = latest_period[:4]  # ex: "2025" de "2025-09-30"

                        # Filtra por 10-Q do mesmo período final E início em Jan do mesmo ano
                        # Isso pega YTD (ex: 2025-01-01 a 2025-09-30 = 9 meses)
                        ytd_values = [
                            v for v in usd_values
                            if v.get("form") == "10-Q"
                            and v.get("end") == latest_period
                            and v.get("start", "").startswith(f"{year}-01")
                        ]

                        if ytd_values:
                            # Pega o YTD
                            extracted_data[field_name] = ytd_values[-1].get("val", 0)
                        else:
                            # Fallback: pega qualquer valor do período final mais recente
                            period_values = [
                                v for v in usd_values
                                if v.get("form") in ("10-Q", "10-K")
                                and v.get("end") == latest_period
                            ]
                            if period_values:
                                # Prefere o período mais longo (YTD > trimestral)
                                sorted_by_duration = sorted(
                                    period_values,
                                    key=lambda x: x.get("start", "9999"),
                                    reverse=False  # Mais antigo start = período mais longo
                                )
                                extracted_data[field_name] = sorted_by_duration[0].get("val", 0)

            except Exception:
                continue

        # Verifica se conseguimos dados mínimos
        if not extracted_data.get("total_assets") or not extracted_data.get("equity"):
            return None

        # === CÁLCULOS DERIVADOS ===

        # 1. Total Liabilities (se não disponível, calcula como Assets - Equity)
        if not extracted_data.get("total_liabilities"):
            assets = extracted_data.get("total_assets", 0)
            equity = extracted_data.get("equity", 0)
            if assets and equity:
                extracted_data["total_liabilities"] = assets - equity

        # 2. Normaliza revenue (algumas empresas usam campo alternativo)
        if not extracted_data.get("revenue") and extracted_data.get("revenue_alt"):
            extracted_data["revenue"] = extracted_data.pop("revenue_alt")
        elif "revenue_alt" in extracted_data:
            del extracted_data["revenue_alt"]

        # Adiciona metadata
        extracted_data["_metadata"] = {
            "source": "SEC XBRL API",
            "period": latest_period,
            "form_type": form_type,
            "cik": cik,
            "extraction_method": "YTD for income statement, point-in-time for balance sheet"
        }

        return extracted_data

    def _fetch_sec_document(self, ticker: str) -> DocumentResult:
        """
        Busca dados financeiros na SEC EDGAR.

        Estratégia de 2 níveis:
        1. XBRL API (preferencial) - Dados estruturados em JSON
        2. HTML Document (fallback) - Para parsing manual

        API Documentation: https://www.sec.gov/developer
        """
        ticker_clean = ticker.upper().strip()

        try:
            # 1. Primeiro, precisamos do CIK (Central Index Key) da empresa
            cik = self._get_sec_cik(ticker_clean)

            if not cik:
                return self._sec_fallback(ticker_clean, "CIK não encontrado")

            # 2. TENTA XBRL PRIMEIRO (dados estruturados - muito mais confiável)
            xbrl_data = self._fetch_sec_xbrl_data(cik)

            if xbrl_data:
                metadata = xbrl_data.pop("_metadata", {})
                return DocumentResult(
                    success=True,
                    asset_type=AssetType.US_STOCK,
                    document_type="XBRL",  # Indica que são dados estruturados
                    metadata={
                        "source": "SEC XBRL",
                        "form_type": metadata.get("form_type", "10-Q"),
                        "filing_date": metadata.get("period"),
                        "cik": cik,
                        "xbrl_data": xbrl_data  # Dados financeiros já extraídos!
                    }
                )

            # 3. FALLBACK: Busca documento HTML tradicional
            submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.HEADERS, timeout=30)

            if response.status_code != 200:
                return self._sec_fallback(ticker_clean, f"HTTP {response.status_code}")

            data = response.json()
            filings = data.get('filings', {}).get('recent', {})

            # Procura pelo 10-Q mais recente
            forms = filings.get('form', [])
            accession_numbers = filings.get('accessionNumber', [])
            primary_documents = filings.get('primaryDocument', [])
            filing_dates = filings.get('filingDate', [])

            for i, form in enumerate(forms):
                if form in ['10-Q', '10-K']:
                    accession = accession_numbers[i].replace('-', '')
                    primary_doc = primary_documents[i]
                    filing_date = filing_dates[i]

                    # Monta a URL do documento
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

                    return DocumentResult(
                        success=True,
                        asset_type=AssetType.US_STOCK,
                        document_url=doc_url,
                        document_type="HTML",  # SEC usa HTML/XBRL
                        metadata={
                            "source": "SEC EDGAR",
                            "form_type": form,
                            "filing_date": filing_date,
                            "cik": cik
                        }
                    )

            return self._sec_fallback(ticker_clean, "Nenhum 10-Q/10-K encontrado")

        except Exception as e:
            return self._sec_fallback(ticker_clean, str(e))

    def _get_sec_cik(self, ticker: str) -> Optional[str]:
        """Busca o CIK da empresa pelo ticker na SEC."""
        try:
            # A SEC mantém um mapeamento ticker -> CIK
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(tickers_url, headers=self.HEADERS, timeout=30)

            if response.status_code == 200:
                data = response.json()
                for item in data.values():
                    if item.get('ticker', '').upper() == ticker:
                        # CIK precisa ter 10 dígitos com zeros à esquerda
                        return str(item['cik_str']).zfill(10)

            return None
        except Exception:
            return None

    def _sec_fallback(self, ticker: str, error: str | None = None) -> DocumentResult:
        """Fallback quando não conseguimos buscar automaticamente na SEC."""

        edgar_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type=10-Q&dateb=&owner=include&count=40"

        msg = f"""
        Não foi possível localizar automaticamente o 10-Q de {ticker} na SEC EDGAR.

        **Busca Manual:**
        1. Acesse [SEC EDGAR]({edgar_url})
        2. Localize o filing mais recente (10-Q = Trimestral, 10-K = Anual)
        3. Baixe o documento
        4. Faça upload do arquivo abaixo
        """

        return DocumentResult(
            success=False,
            asset_type=AssetType.US_STOCK,
            fallback_message=msg.strip(),
            metadata={"manual_search_url": edgar_url, "error": error}
        )

    # =========================================================================
    # MÓDULO CRIPTO (CoinGecko)
    # =========================================================================

    def _fetch_crypto_data(self, ticker: str) -> DocumentResult:
        """
        Busca dados on-chain e sociais via CoinGecko API.

        Para Cripto, não há "balanço". A auditoria é sobre:
        - Developer Activity (commits, contributors)
        - Community Stats (Twitter, Reddit, Telegram)
        - Liquidity (volume, market cap)
        - Tokenomics (supply, distribution)
        """
        # Normaliza o ticker (BTC-USD -> bitcoin, ETH-USD -> ethereum)
        coin_id = self._normalize_crypto_id(ticker)

        try:
            # CoinGecko API (Free Tier)
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            params = {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "true",
                "developer_data": "true",
                "sparkline": "false"
            }

            response = requests.get(url, params=params, headers=self.HEADERS, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Extrai métricas relevantes para "auditoria" cripto
                audit_data = {
                    "name": data.get("name"),
                    "symbol": data.get("symbol", "").upper(),
                    "description": data.get("description", {}).get("en", "")[:500],

                    # Market Data
                    "market_cap_rank": data.get("market_cap_rank"),
                    "market_data": {
                        "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
                        "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                        "total_volume_usd": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                        "price_change_24h": data.get("market_data", {}).get("price_change_percentage_24h"),
                        "price_change_7d": data.get("market_data", {}).get("price_change_percentage_7d"),
                        "price_change_30d": data.get("market_data", {}).get("price_change_percentage_30d"),
                    },

                    # Supply (Tokenomics)
                    "supply": {
                        "circulating": data.get("market_data", {}).get("circulating_supply"),
                        "total": data.get("market_data", {}).get("total_supply"),
                        "max": data.get("market_data", {}).get("max_supply"),
                    },

                    # Developer Activity
                    "developer_data": data.get("developer_data", {}),

                    # Community
                    "community_data": data.get("community_data", {}),

                    # Links
                    "links": {
                        "homepage": data.get("links", {}).get("homepage", [None])[0],
                        "whitepaper": data.get("links", {}).get("whitepaper"),
                        "github": data.get("links", {}).get("repos_url", {}).get("github", []),
                    },

                    # Scores (CoinGecko calcula)
                    "scores": {
                        "coingecko_score": data.get("coingecko_score"),
                        "developer_score": data.get("developer_score"),
                        "community_score": data.get("community_score"),
                        "liquidity_score": data.get("liquidity_score"),
                    }
                }

                return DocumentResult(
                    success=True,
                    asset_type=AssetType.CRYPTO,
                    document_type="JSON",
                    metadata={
                        "source": "CoinGecko",
                        "audit_data": audit_data,
                        "whitepaper_url": audit_data["links"]["whitepaper"]
                    }
                )

            return self._crypto_fallback(ticker, f"HTTP {response.status_code}")

        except Exception as e:
            return self._crypto_fallback(ticker, str(e))

    def _normalize_crypto_id(self, ticker: str) -> str:
        """Converte ticker para CoinGecko ID."""
        # Mapeamento dos principais
        mapping = {
            "BTC": "bitcoin",
            "BTC-USD": "bitcoin",
            "ETH": "ethereum",
            "ETH-USD": "ethereum",
            "SOL": "solana",
            "SOL-USD": "solana",
            "DOGE": "dogecoin",
            "DOGE-USD": "dogecoin",
            "XRP": "ripple",
            "XRP-USD": "ripple",
            "BNB": "binancecoin",
            "BNB-USD": "binancecoin",
            "ADA": "cardano",
            "ADA-USD": "cardano",
            "DOT": "polkadot",
            "DOT-USD": "polkadot",
            "AVAX": "avalanche-2",
            "AVAX-USD": "avalanche-2",
            "MATIC": "matic-network",
            "MATIC-USD": "matic-network",
            "LINK": "chainlink",
            "LINK-USD": "chainlink",
            "UNI": "uniswap",
            "UNI-USD": "uniswap",
        }

        ticker_upper = ticker.upper()
        return mapping.get(ticker_upper, ticker.lower().replace("-usd", ""))

    def _crypto_fallback(self, ticker: str, error: str | None = None) -> DocumentResult:
        """Fallback para cripto."""
        msg = f"""
        Não foi possível obter dados de {ticker} da CoinGecko.

        **Informações:**
        - Criptoativos não possuem balanços trimestrais como ações.
        - A auditoria é baseada em dados on-chain, atividade de desenvolvimento e métricas sociais.

        **Busca Manual:**
        - [CoinGecko](https://www.coingecko.com/)
        - [CoinMarketCap](https://coinmarketcap.com/)
        """

        return DocumentResult(
            success=False,
            asset_type=AssetType.CRYPTO,
            fallback_message=msg.strip(),
            metadata={"error": error}
        )

    # =========================================================================
    # MÓDULO ETF (Yahoo Finance)
    # =========================================================================

    def _fetch_etf_data(self, ticker: str) -> DocumentResult:
        """
        Busca dados de composição de ETFs via yfinance.

        ETFs não têm EBITDA. Eles têm:
        - Holdings (o que tem dentro)
        - Sector Weightings
        - Fees (Expense Ratio)
        """
        try:
            etf = yf.Ticker(ticker)
            info = etf.info

            # Dados básicos
            etf_data = {
                "name": info.get("longName", info.get("shortName", ticker)),
                "category": info.get("category", "N/A"),
                "fund_family": info.get("fundFamily", "N/A"),

                # Fees
                "expense_ratio": info.get("annualReportExpenseRatio"),
                "total_assets": info.get("totalAssets"),
                "nav_price": info.get("navPrice"),

                # Yield
                "yield": info.get("yield"),
                "ytd_return": info.get("ytdReturn"),
                "three_year_return": info.get("threeYearAverageReturn"),
                "five_year_return": info.get("fiveYearAverageReturn"),

                # Holdings (Top 10)
                "holdings": [],

                # Sector Weights
                "sector_weightings": {}
            }

            # Tenta pegar holdings
            try:
                holdings_df = getattr(etf, 'get_holdings', lambda: None)()
                if holdings_df is not None and hasattr(holdings_df, 'empty') and not holdings_df.empty:
                    # Converte para lista de dicts
                    top_holdings = holdings_df.head(10).to_dict('records')
                    etf_data["holdings"] = top_holdings
            except Exception:
                pass

            # Sector weightings (se disponível)
            sector_weights = info.get("sectorWeightings", {})
            if sector_weights:
                etf_data["sector_weightings"] = sector_weights

            return DocumentResult(
                success=True,
                asset_type=AssetType.US_ETF,
                document_type="JSON",
                metadata={
                    "source": "Yahoo Finance",
                    "etf_data": etf_data
                }
            )

        except Exception as e:
            return self._etf_fallback(ticker, str(e))

    def _etf_fallback(self, ticker: str, error: str | None = None) -> DocumentResult:
        """Fallback para ETFs."""
        msg = f"""
        Não foi possível obter dados de {ticker}.

        **Informações:**
        - ETFs não possuem demonstrações financeiras como empresas.
        - A análise é baseada em composição (holdings), taxas e performance.

        **Busca Manual:**
        - [ETF.com](https://www.etf.com/stock/{ticker})
        - [Yahoo Finance](https://finance.yahoo.com/quote/{ticker})
        """

        return DocumentResult(
            success=False,
            asset_type=AssetType.US_ETF,
            fallback_message=msg.strip(),
            metadata={"error": error}
        )


# Instância singleton para uso global
titan_router = TitanRouter()
