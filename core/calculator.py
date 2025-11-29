import logging
from typing import Dict, List, Optional
from .extractor import FinancialStatement

logger = logging.getLogger("TitanCalculator")


class FinancialHealthReport:
    """Objeto de transferência de dados (DTO) para o relatório final."""
    def __init__(self, score_z: float, solvency_status: str, dupont: Dict, forensic_flags: List[str],
                 piotroski: Optional[Dict] = None, audit_debug: Optional[Dict] = None):
        self.altman_z_score = score_z
        self.solvency_status = solvency_status
        self.dupont_analysis = dupont
        self.forensic_flags = forensic_flags
        self.piotroski_score = piotroski  # Novo: Piotroski F-Score (0-9)
        self.audit_debug = audit_debug  # Novo: Dados brutos e fórmulas para auditoria


class TitanMathEngine:
    """
    Motor de cálculo financeiro determinístico.
    Padrão Strategy Pattern - Análise adaptativa por setor.

    Setores suportados:
    - Banking: Foco em Basileia, NPL, ROE
    - Insurance: Foco em Sinistralidade, Índice Combinado
    - Corporate: Z-Score, EBITDA, Liquidez
    """

    @staticmethod
    def safe_div(n: Optional[float], d: Optional[float], default: float = 0.0) -> float:
        """Divisão segura para evitar ZeroDivisionError."""
        if n is None or d is None:
            return default
        return n / d if d != 0 else default

    @staticmethod
    def _human_format(num: Optional[float]) -> str:
        """Formata números grandes para leitura humana (ex: 1.5 bi)."""
        if num is None:
            return "N/A"
        num = float(f"{num:.3g}")
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        suffix = ['', 'mil', 'mi', 'bi', 'tri'][magnitude]
        return f"R$ {num:.1f} {suffix}"

    def analyze(self, data: FinancialStatement) -> FinancialHealthReport:
        """
        Análise principal - Seleciona estratégia baseada no setor.
        """
        logger.info(f"Analisando {data.company_name} | Setor: {data.sector}")

        flags = []
        z_score = 0.0
        status = "N/A"

        # --- SELEÇÃO DE ESTRATÉGIA POR SETOR ---
        if data.sector == "Banking":
            z_score, status, sector_flags = self._analyze_banking(data)
            flags.extend(sector_flags)
        elif data.sector == "Insurance":
            z_score, status, sector_flags = self._analyze_insurance(data)
            flags.extend(sector_flags)
        else:  # Corporate (default)
            z_score, status, sector_flags = self._analyze_corporate(data)
            flags.extend(sector_flags)

        # --- CHECK UNIVERSAL: PL NEGATIVO ---
        if data.equity < 0:
            flags.append("Passivo a Descoberto: Patrimônio Líquido negativo. Insolvência técnica.")

        # --- CÁLCULO UNIVERSAL: DUPONT ANALYSIS ---
        # DuPont funciona para todos os setores
        net_margin = self.safe_div(data.net_income, data.revenue)
        asset_turnover = self.safe_div(data.revenue, data.total_assets)
        fin_leverage = self.safe_div(data.total_assets, data.equity) if data.equity > 0 else 0.0

        roe = net_margin * asset_turnover * fin_leverage

        # Proxy Basileia: PL / Ativos (útil quando banco não reporta Basileia)
        capital_ratio = self.safe_div(data.equity, data.total_assets)

        dupont_data = {
            "net_margin": round(net_margin * 100, 2),
            "asset_turnover": round(asset_turnover, 2),
            "financial_leverage": round(fin_leverage, 2),
            "roe": round(roe * 100, 2),
            "capital_ratio": round(capital_ratio, 4)  # Proxy Basileia para Banking
        }

        # --- PIOTROSKI F-SCORE (Corporate Only) ---
        piotroski_result = None
        if data.sector == "Corporate":
            piotroski_result = self._calculate_piotroski(data)

        # --- MÉTRICAS COMPLEMENTARES ---
        complementary = self._calculate_complementary_metrics(data)

        # --- AUDIT DEBUG MODE ---
        audit_debug = self._build_audit_debug(data, z_score, dupont_data, piotroski_result, complementary)

        return FinancialHealthReport(
            score_z=round(z_score, 2),
            solvency_status=status,
            dupont=dupont_data,
            forensic_flags=flags,
            piotroski=piotroski_result,
            audit_debug=audit_debug
        )

    # =========================================================================
    # ESTRATÉGIA: BANKING
    # =========================================================================
    def _analyze_banking(self, data: FinancialStatement) -> tuple:
        """Análise específica para Bancos e Fintechs."""
        flags = ["Setor Bancário - Análise focada em Basileia, Inadimplência e ROE."]

        # Score baseado em métricas bancárias (0-3)
        score = 0.0

        # 1. Índice de Basileia (Capital Adequacy)
        if data.basel_ratio is not None:
            if data.basel_ratio >= 0.11:  # >= 11% é saudável
                score += 1.0
            elif data.basel_ratio >= 0.08:  # >= 8% é mínimo regulatório
                score += 0.5
                flags.append(f"⚠️ Basileia no Limite: {data.basel_ratio*100:.1f}%. Próximo do mínimo regulatório (8%).")
            else:
                flags.append(f"🚨 Basileia Crítico: {data.basel_ratio*100:.1f}%. Abaixo do mínimo regulatório!")
        else:
            # Proxy: PL / Ativos
            capital_ratio = self.safe_div(data.equity, data.total_assets)
            if capital_ratio >= 0.10:
                score += 0.8
            elif capital_ratio >= 0.05:
                score += 0.4
                flags.append(f"⚠️ Alavancagem Alta: PL representa apenas {capital_ratio*100:.1f}% dos ativos.")
            else:
                flags.append(f"🚨 Alavancagem Crítica: PL representa apenas {capital_ratio*100:.1f}% dos ativos.")

        # 2. Inadimplência (NPL)
        if data.non_performing_loans is not None:
            if data.non_performing_loans <= 0.03:  # <= 3% é bom
                score += 1.0
            elif data.non_performing_loans <= 0.05:  # <= 5% é aceitável
                score += 0.5
                flags.append(f"⚠️ Inadimplência Elevada: NPL de {data.non_performing_loans*100:.1f}%.")
            else:
                flags.append(f"🚨 Carteira Podre: NPL de {data.non_performing_loans*100:.1f}%. Risco de crédito elevado.")
        else:
            score += 0.5  # Sem dados, neutro

        # 3. ROE Bancário (> 15% é bom para bancos)
        roe = self.safe_div(data.net_income, data.equity)
        if roe >= 0.15:
            score += 1.0
        elif roe >= 0.10:
            score += 0.5
        elif roe < 0.05 and roe >= 0:
            flags.append(f"⚠️ ROE Fraco: {roe*100:.1f}%. Rentabilidade abaixo do esperado para bancos.")

        # Status baseado no score
        if score >= 2.5:
            status = "Banco Saudável"
        elif score >= 1.5:
            status = "Banco em Alerta"
        else:
            status = "Banco em Risco"

        return score, status, flags

    # =========================================================================
    # ESTRATÉGIA: INSURANCE
    # =========================================================================
    def _analyze_insurance(self, data: FinancialStatement) -> tuple:
        """Análise específica para Seguradoras."""
        flags = ["Setor de Seguros - Análise focada em Sinistralidade e Índice Combinado."]

        score = 0.0

        # 1. Sinistralidade (Loss Ratio)
        if data.loss_ratio is not None:
            if data.loss_ratio <= 0.65:  # <= 65% é excelente
                score += 1.5
            elif data.loss_ratio <= 0.75:  # <= 75% é aceitável
                score += 0.8
                flags.append(f"⚠️ Sinistralidade Alta: {data.loss_ratio*100:.1f}%. Margens técnicas pressionadas.")
            else:
                flags.append(f"🚨 Sinistralidade Crítica: {data.loss_ratio*100:.1f}%. Operação de seguros dá prejuízo técnico.")
        else:
            score += 0.5  # Sem dados, neutro

        # 2. Índice Combinado (Combined Ratio)
        if data.combined_ratio is not None:
            if data.combined_ratio <= 0.95:  # < 95% gera lucro operacional
                score += 1.5
            elif data.combined_ratio <= 1.00:  # <= 100% é breakeven
                score += 0.5
                flags.append(f"⚠️ Índice Combinado no Limite: {data.combined_ratio*100:.1f}%. Depende de resultado financeiro.")
            else:
                flags.append(f"🚨 Índice Combinado > 100%: {data.combined_ratio*100:.1f}%. Operação de seguros dá prejuízo!")
        else:
            score += 0.5

        # 3. ROE (> 12% é bom para seguradoras)
        roe = self.safe_div(data.net_income, data.equity)
        if roe >= 0.12:
            score += 1.0
        elif roe >= 0.08:
            score += 0.5
        elif roe < 0.05 and roe >= 0:
            flags.append(f"⚠️ ROE Fraco: {roe*100:.1f}%. Rentabilidade abaixo do esperado.")

        # Status
        if score >= 2.5:
            status = "Seguradora Saudável"
        elif score >= 1.5:
            status = "Seguradora em Alerta"
        else:
            status = "Seguradora em Risco"

        return score, status, flags

    # =========================================================================
    # ESTRATÉGIA: CORPORATE
    # =========================================================================
    def _analyze_corporate(self, data: FinancialStatement) -> tuple:
        """Análise para empresas gerais (Varejo, Indústria, Tech)."""
        flags = ["Setor Corporativo - Análise via Altman Z-Score."]

        z_score = 0.0

        # Só calcula Z-Score se tiver dados de circulante
        if data.current_assets is not None and data.current_liabilities is not None:
            wc = data.current_assets - data.current_liabilities
            ebit_val = data.ebit if data.ebit else data.net_income
            total_liab = data.total_liabilities or (data.total_assets - data.equity)
            retained = data.retained_earnings or 0.0

            x1 = self.safe_div(wc, data.total_assets)
            x2 = self.safe_div(retained, data.total_assets)
            x3 = self.safe_div(ebit_val, data.total_assets)
            x4 = self.safe_div(data.equity, total_liab)

            z_score = (6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4)
        else:
            flags.append("⚠️ Dados de Ativo/Passivo Circulante ausentes. Z-Score aproximado.")
            # Z-Score simplificado
            ebit_val = data.ebit if data.ebit else data.net_income
            total_liab = data.total_liabilities or (data.total_assets - data.equity)
            x3 = self.safe_div(ebit_val, data.total_assets)
            x4 = self.safe_div(data.equity, total_liab) if total_liab > 0 else 0
            z_score = (6.72 * x3) + (1.05 * x4)

        # Status baseado no Z-Score
        if z_score > 2.6:
            status = "Zona Segura"
        elif z_score > 1.1:
            status = "Zona de Alerta (Grey Zone)"
        else:
            status = "Zona de Perigo (Insolvência)"

        # --- CONTEXTUALIZAÇÃO DO Z-SCORE (TECH GIANTS) ---
        # O Z-Score de Altman (1968) foi desenhado para manufaturas.
        # Tech companies com Working Capital negativo INTENCIONAL geram falsos positivos.

        is_tech_giant_pattern = self._detect_tech_giant_pattern(data, z_score)

        if is_tech_giant_pattern and z_score < 1.8:
            # Modifica o status para refletir a realidade
            status = "Z-Score Baixo (Otimização de Capital)"
            flags.append(
                f"ℹ️ Z-Score de {z_score:.2f} NÃO indica risco real de falência. "
                f"Empresa opera com Working Capital negativo por estratégia (recebe antes de pagar). "
                f"Lucro positivo e caixa abundante contradizem risco de insolvência."
            )

        # --- FLAGS ESPECÍFICAS CORPORATE ---

        # Check: EBITDA vs Lucro
        if data.ebitda is not None and data.net_income is not None:
            if data.ebitda > 0 and data.net_income < 0:
                diff = data.ebitda - data.net_income
                flags.append(f"Divergência EBITDA/Lucro: Operação gera caixa, mas {self._human_format(diff)} consumidos por Juros/D&A.")

        # Check: Liquidez
        if data.current_assets is not None and data.current_liabilities is not None:
            current_ratio = self.safe_div(data.current_assets, data.current_liabilities)
            if 0 < current_ratio < 1.0:
                # Se for tech giant, contextualiza
                if is_tech_giant_pattern:
                    flags.append(
                        f"ℹ️ Índice Corrente de {current_ratio:.2f} (< 1.0) é INTENCIONAL. "
                        f"Empresa otimiza capital de giro - recebe dos clientes antes de pagar fornecedores."
                    )
                else:
                    flags.append(f"⚠️ Crise de Liquidez: Índice Corrente de {current_ratio:.2f}. Capital de Giro Negativo.")

        # Check: Margem Operacional
        if data.ebit is not None:
            op_margin = self.safe_div(data.ebit, data.revenue)
            if -1 < op_margin < 0.05:
                flags.append(f"⚠️ Margem Operacional Crítica: {op_margin*100:.1f}%. Operação core gera pouco valor.")

        return z_score, status, flags

    def _detect_tech_giant_pattern(self, data: 'FinancialStatement', z_score: float) -> bool:
        """
        Detecta se a empresa segue o padrão de "Tech Giant" onde Z-Score baixo
        não indica risco real de insolvência.

        Critérios:
        1. Net Income positivo (empresa é lucrativa)
        2. Total Assets > $50 bilhões (escala grande)
        3. Cash abundante OU Net Income alto
        4. Working Capital negativo (current_assets < current_liabilities)
        """
        # Critério 1: Empresa lucrativa
        if data.net_income is None or data.net_income <= 0:
            return False

        # Critério 2: Grande escala (> $50 bi em ativos)
        if data.total_assets < 50_000_000_000:  # 50 bilhões
            return False

        # Critério 3: Working Capital negativo intencional
        if data.current_assets and data.current_liabilities:
            if data.current_assets >= data.current_liabilities:
                return False  # WC positivo, não é o padrão tech giant

        # Critério 4: Caixa abundante OU Lucro muito alto
        has_cash_cushion = False

        # Verifica se tem campo cash
        cash = getattr(data, 'cash', None)
        if cash and cash > 10_000_000_000:  # > $10 bi em caixa
            has_cash_cushion = True

        # Lucro alto em relação aos ativos (ROA > 5%)
        roa = self.safe_div(data.net_income, data.total_assets)
        if roa > 0.05:
            has_cash_cushion = True

        return has_cash_cushion

    # =========================================================================
    # PIOTROSKI F-SCORE (9 PONTOS)
    # =========================================================================
    def _calculate_piotroski(self, data: 'FinancialStatement') -> Dict:
        """
        Calcula o Piotroski F-Score (0-9 pontos).

        O F-Score avalia a força financeira de uma empresa baseado em 9 critérios:

        PROFITABILITY (4 pontos):
        1. ROA > 0 (Net Income / Total Assets positivo)
        2. Operating Cash Flow > 0 (usamos proxy: Net Income + D&A)
        3. ROA melhorando (ano a ano) - simplificado: ROA > 3%
        4. Accruals: Cash Flow > Net Income (qualidade dos lucros)

        LEVERAGE/LIQUIDITY (3 pontos):
        5. Redução de dívida de longo prazo (proxy: Debt/Assets < 50%)
        6. Current Ratio > 1 (melhoria de liquidez)
        7. Sem emissão de novas ações (proxy: retained_earnings positivo)

        EFFICIENCY (2 pontos):
        8. Gross Margin melhorando (proxy: gross margin > 30%)
        9. Asset Turnover melhorando (Revenue/Assets > 0.5)

        Interpretação:
        - 8-9: Empresa FORTE (compra)
        - 5-7: Empresa NEUTRA (hold)
        - 0-4: Empresa FRACA (evitar)
        """
        score = 0
        breakdown = {}

        # === PROFITABILITY (4 pontos) ===

        # 1. ROA Positivo
        roa = self.safe_div(data.net_income, data.total_assets)
        breakdown["roa"] = {
            "value": round(roa * 100, 2),
            "formula": f"Net Income ({self._human_format(data.net_income)}) / Total Assets ({self._human_format(data.total_assets)})",
            "threshold": "> 0%",
            "pass": roa > 0
        }
        if roa > 0:
            score += 1

        # 2. Operating Cash Flow Positivo (proxy: usamos EBITDA se disponível, senão Net Income)
        ocf_proxy = data.ebitda if data.ebitda else data.net_income
        breakdown["operating_cash_flow"] = {
            "value": self._human_format(ocf_proxy),
            "formula": "EBITDA (ou Net Income como proxy)",
            "threshold": "> 0",
            "pass": ocf_proxy > 0 if ocf_proxy else False
        }
        if ocf_proxy and ocf_proxy > 0:
            score += 1

        # 3. ROA Melhorando (proxy simplificado: ROA > 3% indica empresa saudável)
        roa_improving = roa > 0.03
        breakdown["roa_trend"] = {
            "value": f"{round(roa * 100, 2)}%",
            "formula": "ROA atual > 3% (proxy para tendência positiva)",
            "threshold": "> 3%",
            "pass": roa_improving
        }
        if roa_improving:
            score += 1

        # 4. Accruals (Qualidade dos Lucros) - CFO > Net Income
        # Proxy: Se EBITDA > Net Income, os lucros têm qualidade (não são só contábeis)
        accruals_quality = False
        if data.ebitda and data.net_income:
            accruals_quality = data.ebitda > data.net_income
        breakdown["accruals"] = {
            "value": f"EBITDA: {self._human_format(data.ebitda)}, Net Income: {self._human_format(data.net_income)}",
            "formula": "EBITDA > Net Income (lucros de qualidade)",
            "threshold": "EBITDA > Net Income",
            "pass": accruals_quality
        }
        if accruals_quality:
            score += 1

        # === LEVERAGE / LIQUIDITY (3 pontos) ===

        # 5. Redução de Dívida (proxy: Debt/Assets < 50%)
        total_debt = (data.long_term_debt or 0) + (data.short_term_debt or 0)
        if total_debt == 0:
            total_debt = (data.total_liabilities or 0) * 0.5  # Estimativa conservadora
        debt_ratio = self.safe_div(total_debt, data.total_assets)
        low_debt = debt_ratio < 0.5
        breakdown["leverage"] = {
            "value": f"{round(debt_ratio * 100, 2)}%",
            "formula": f"Total Debt ({self._human_format(total_debt)}) / Total Assets ({self._human_format(data.total_assets)})",
            "threshold": "< 50%",
            "pass": low_debt
        }
        if low_debt:
            score += 1

        # 6. Current Ratio > 1
        current_ratio = self.safe_div(data.current_assets, data.current_liabilities)
        good_liquidity = current_ratio > 1.0 if current_ratio else False
        breakdown["current_ratio"] = {
            "value": round(current_ratio, 2) if current_ratio else "N/A",
            "formula": f"Current Assets ({self._human_format(data.current_assets)}) / Current Liabilities ({self._human_format(data.current_liabilities)})",
            "threshold": "> 1.0",
            "pass": good_liquidity
        }
        if good_liquidity:
            score += 1

        # 7. Sem Diluição (proxy: Retained Earnings positivo = não precisou emitir ações)
        no_dilution = (data.retained_earnings or 0) > 0
        breakdown["dilution"] = {
            "value": self._human_format(data.retained_earnings),
            "formula": "Retained Earnings > 0 (não precisou emitir ações)",
            "threshold": "> 0",
            "pass": no_dilution
        }
        if no_dilution:
            score += 1

        # === OPERATING EFFICIENCY (2 pontos) ===

        # 8. EBIT Margin (Operating Margin > 10% indica eficiência operacional)
        ebit_margin = self.safe_div(data.ebit, data.revenue) if data.ebit else self.safe_div(data.net_income, data.revenue) * 1.3
        good_margin = ebit_margin > 0.10
        breakdown["ebit_margin"] = {
            "value": f"{round(ebit_margin * 100, 2)}%",
            "formula": f"EBIT ({self._human_format(data.ebit)}) / Revenue ({self._human_format(data.revenue)})",
            "threshold": "> 10%",
            "pass": good_margin
        }
        if good_margin:
            score += 1

        # 9. Asset Turnover (Revenue / Assets > 0.3)
        asset_turnover = self.safe_div(data.revenue, data.total_assets)
        good_turnover = asset_turnover > 0.3
        breakdown["asset_turnover"] = {
            "value": round(asset_turnover, 2),
            "formula": f"Revenue ({self._human_format(data.revenue)}) / Total Assets ({self._human_format(data.total_assets)})",
            "threshold": "> 0.3",
            "pass": good_turnover
        }
        if good_turnover:
            score += 1

        # === INTERPRETAÇÃO ===
        if score >= 8:
            interpretation = "FORTE - Empresa financeiramente sólida (compra)"
            strength_level = "strong"  # Mapeia para ícone CSS na UI
        elif score >= 5:
            interpretation = "NEUTRA - Fundamentos mistos (hold)"
            strength_level = "neutral"
        else:
            interpretation = "FRACA - Fundamentos fracos (evitar)"
            strength_level = "weak"

        return {
            "score": score,
            "max_score": 9,
            "interpretation": interpretation,
            "strength_level": strength_level,  # Para mapeamento de ícones CSS
            "breakdown": breakdown,
            "categories": {
                "profitability": sum([breakdown["roa"]["pass"], breakdown["operating_cash_flow"]["pass"],
                                     breakdown["roa_trend"]["pass"], breakdown["accruals"]["pass"]]),
                "leverage_liquidity": sum([breakdown["leverage"]["pass"], breakdown["current_ratio"]["pass"],
                                          breakdown["dilution"]["pass"]]),
                "efficiency": sum([breakdown["ebit_margin"]["pass"], breakdown["asset_turnover"]["pass"]])
            }
        }

    # =========================================================================
    # MÉTRICAS COMPLEMENTARES
    # =========================================================================
    def _calculate_complementary_metrics(self, data: 'FinancialStatement') -> Dict:
        """
        Calcula métricas complementares para enriquecer a análise.
        """
        metrics = {}

        # Current Ratio
        if data.current_assets and data.current_liabilities:
            current_ratio = self.safe_div(data.current_assets, data.current_liabilities)
            metrics["current_ratio"] = {
                "value": round(current_ratio, 2),
                "interpretation": "Saudável" if current_ratio > 1.5 else ("Adequado" if current_ratio > 1.0 else "Risco de Liquidez"),
                "formula": "Ativo Circulante / Passivo Circulante"
            }

        # Quick Ratio (Acid Test) - sem estoque
        # Proxy: Current Assets * 0.7 (assumindo 30% é estoque)
        if data.current_assets and data.current_liabilities:
            quick_assets = data.current_assets * 0.7  # Proxy sem estoque
            if data.cash:
                quick_assets = data.cash + (data.current_assets - data.cash) * 0.5
            quick_ratio = self.safe_div(quick_assets, data.current_liabilities)
            metrics["quick_ratio"] = {
                "value": round(quick_ratio, 2),
                "interpretation": "Boa liquidez imediata" if quick_ratio > 1.0 else "Liquidez imediata baixa",
                "formula": "(Ativo Circulante - Estoque) / Passivo Circulante"
            }

        # Debt-to-Equity Ratio
        total_debt = (data.long_term_debt or 0) + (data.short_term_debt or 0)
        if total_debt == 0 and data.total_liabilities:
            total_debt = data.total_liabilities
        if data.equity and data.equity > 0:
            debt_equity = self.safe_div(total_debt, data.equity)
            metrics["debt_to_equity"] = {
                "value": round(debt_equity, 2),
                "interpretation": "Baixo endividamento" if debt_equity < 1.0 else ("Moderado" if debt_equity < 2.0 else "Alto endividamento"),
                "formula": "Dívida Total / Patrimônio Líquido"
            }

        # Interest Coverage (se tiver EBIT e dados de dívida)
        if data.ebit and total_debt > 0:
            # Proxy: assumindo juros = 5% da dívida
            interest_expense = total_debt * 0.05
            interest_coverage = self.safe_div(data.ebit, interest_expense)
            metrics["interest_coverage"] = {
                "value": round(interest_coverage, 2),
                "interpretation": "Excelente" if interest_coverage > 5 else ("Adequado" if interest_coverage > 2 else "Preocupante"),
                "formula": "EBIT / Despesas com Juros"
            }

        # ROA (Return on Assets)
        roa = self.safe_div(data.net_income, data.total_assets)
        metrics["roa"] = {
            "value": round(roa * 100, 2),
            "interpretation": "Excelente" if roa > 0.10 else ("Bom" if roa > 0.05 else ("Adequado" if roa > 0.02 else "Fraco")),
            "formula": "Lucro Líquido / Ativo Total"
        }

        return metrics

    # =========================================================================
    # AUDIT DEBUG MODE
    # =========================================================================
    def _build_audit_debug(self, data: 'FinancialStatement', z_score: float,
                           dupont: Dict, piotroski: Optional[Dict], complementary: Dict) -> Dict:
        """
        Constrói um objeto detalhado para auditoria dos cálculos.
        Permite ao usuário verificar cada passo e os dados brutos usados.
        """
        # Valores brutos recebidos
        raw_data = {
            "company_name": data.company_name,
            "period": data.period,
            "sector": data.sector,
            "currency": data.currency,
            "total_assets": data.total_assets,
            "equity": data.equity,
            "net_income": data.net_income,
            "revenue": data.revenue,
            "current_assets": data.current_assets,
            "current_liabilities": data.current_liabilities,
            "total_liabilities": data.total_liabilities,
            "retained_earnings": data.retained_earnings,
            "ebit": data.ebit,
            "ebitda": data.ebitda,
            "cash": getattr(data, 'cash', None),
            "long_term_debt": getattr(data, 'long_term_debt', None),
            "short_term_debt": getattr(data, 'short_term_debt', None),
        }

        # Cálculos intermediários do Z-Score
        wc = (data.current_assets or 0) - (data.current_liabilities or 0)
        total_liab = data.total_liabilities or (data.total_assets - data.equity)
        ebit_val = data.ebit if data.ebit else data.net_income

        x1 = self.safe_div(wc, data.total_assets)
        x2 = self.safe_div(data.retained_earnings or 0, data.total_assets)
        x3 = self.safe_div(ebit_val, data.total_assets)
        x4 = self.safe_div(data.equity, total_liab) if total_liab > 0 else 0

        z_score_calculation = {
            "formula": "Z = 6.56×X1 + 3.26×X2 + 6.72×X3 + 1.05×X4",
            "variables": {
                "X1 (Working Capital / Total Assets)": {
                    "calculation": f"({self._human_format(wc)}) / ({self._human_format(data.total_assets)})",
                    "result": round(x1, 4)
                },
                "X2 (Retained Earnings / Total Assets)": {
                    "calculation": f"({self._human_format(data.retained_earnings)}) / ({self._human_format(data.total_assets)})",
                    "result": round(x2, 4)
                },
                "X3 (EBIT / Total Assets)": {
                    "calculation": f"({self._human_format(ebit_val)}) / ({self._human_format(data.total_assets)})",
                    "result": round(x3, 4)
                },
                "X4 (Equity / Total Liabilities)": {
                    "calculation": f"({self._human_format(data.equity)}) / ({self._human_format(total_liab)})",
                    "result": round(x4, 4)
                }
            },
            "final_calculation": f"6.56×{round(x1, 4)} + 3.26×{round(x2, 4)} + 6.72×{round(x3, 4)} + 1.05×{round(x4, 4)}",
            "result": round(z_score, 2),
            "thresholds": {
                "> 2.6": "Zona Segura",
                "1.1 - 2.6": "Grey Zone (Alerta)",
                "< 1.1": "Zona de Perigo"
            }
        }

        return {
            "raw_data_received": raw_data,
            "z_score_calculation": z_score_calculation,
            "dupont_analysis": dupont,
            "piotroski_breakdown": piotroski["breakdown"] if piotroski else None,
            "complementary_metrics": complementary,
            "data_source": "XBRL API / PDF Extraction / Manual Input",
            "calculation_timestamp": None,  # Pode adicionar datetime se necessário
            "verification_note": "Compare os valores brutos com o documento original para validar a extração."
        }