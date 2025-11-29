import os
import re
import streamlit as st
from pypdf import PdfReader
from dotenv import load_dotenv
from typing import Dict, Any

# --- IMPORTACAO DO CORE (A Magica acontece aqui) ---
from core.extractor import TitanExtractor
from core.calculator import TitanMathEngine
from core.auditor import TitanAuditor, AuditVerdict
from core.market_data import MarketDataService
from core.market_map import MACRO_ASSETS, POPULAR_TICKERS
from core.router import titan_router, AssetType

# --- IMPORTACAO DO DESIGN SYSTEM ---
from ui import (
    inject_css,
    metric_card,
    verdict_hero,
    section_header,
    alert_box,
    argument_card,
    page_header,
    badge,
    ICONS
)

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

st.set_page_config(
    page_title="Titan Financial Auditor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa estado da sessão
if "selected_example_path" not in st.session_state:
    st.session_state.selected_example_path = None
if "selected_example_name" not in st.session_state:
    st.session_state.selected_example_name = None
if "ticker_search" not in st.session_state:
    st.session_state.ticker_search = None

# --- DEFINIÇÃO DE MODELOS (Mantida conforme solicitado) ---
LLM_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "Grok (xAI) - Reasoning": {
        "model": "grok-4-1-fast-reasoning",
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
        "icon": "",
        "desc": "Alta velocidade com capacidade de raciocínio profundo."
    },
    "OpenAI - GPT-5": {
        "model": "gpt-5",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "icon": "",
        "desc": "Modelo SOTA (State of the Art) para tarefas complexas."
    },
    "OpenAI - GPT-4.1 (Mini)": {
        "model": "gpt-4.1-mini",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "icon": "",
        "desc": "Equilíbrio ideal entre custo e performance."
    }
}

# --- FUNÇÕES UTILITÁRIAS ---

def clean_text(text: str) -> str:
    """
    Remove caracteres de LaTeX que podem quebrar a renderização do Streamlit.
    Exemplos de problemas: R$6,2bilho~es, \\textbf, $240$
    """
    if not text:
        return text

    # Remove ~ usado como espaço não-quebrável do LaTeX
    text = text.replace("~", " ")

    # Remove comandos LaTeX comuns (\textbf, \textit, etc.)
    text = re.sub(r'\\text\w+\{([^}]*)\}', r'\1', text)

    # Remove $ isolados que não fazem parte de valores monetários
    # Mantém "R$ 100" mas remove "$x$" (LaTeX math mode)
    text = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\$', r'\1', text)

    # Remove barras invertidas órfãs
    text = re.sub(r'\\([^\\])', r'\1', text)

    # Normaliza múltiplos espaços
    text = re.sub(r' +', ' ', text)

    return text.strip()


def extract_text_from_pdf(file_input) -> str:
    try:
        reader = PdfReader(file_input)

        # Verifica se está criptografado (mesmo sem senha)
        if reader.is_encrypted:
            try:
                # Tenta descriptografar com senha vazia (padrão de muitos PDFs corporativos)
                reader.decrypt("")
            except Exception:
                # Se falhar, avisa, mas tenta seguir se possível
                pass

        text = []
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text.append(content)

        final_text = "\n".join(text)

        # Sanity Check: Se extraiu muito pouco texto, pode ser imagem
        if len(final_text) < 100:
            st.warning("Aviso: O PDF parece conter pouco texto extraível (pode ser imagem escaneada). A análise pode ser comprometida.")

        return final_text

    except Exception as e:
        error_msg = str(e)
        if "cryptography" in error_msg:
            st.error("Erro de Dependência: O servidor precisa da biblioteca 'cryptography' para ler este PDF seguro. Instale com `pip install cryptography`.")
        else:
            st.error(f"Erro crítico ao ler PDF: {error_msg}")
        return ""

def get_api_credentials(provider_key: str):
    """Recupera credenciais seguras para instanciar os agentes.
    Suporta tanto .env (local) quanto st.secrets (Streamlit Cloud).
    """
    config = LLM_PROVIDERS.get(provider_key)
    if not config: return None, None, None

    env_var = config["api_key_env"]

    # Tenta st.secrets primeiro (Streamlit Cloud), depois os.getenv (.env local)
    key = None
    try:
        # Streamlit Cloud - secrets.toml existe
        if hasattr(st, 'secrets') and len(st.secrets) > 0 and env_var in st.secrets:
            key = st.secrets[env_var]
    except Exception:
        pass  # Ignora se secrets não existir

    if not key:
        # Fallback para .env local
        key = os.getenv(env_var)

    if not key:
        st.error(f"Chave {env_var} não encontrada. Configure no .env (local) ou em Secrets (Streamlit Cloud).")
        st.stop()

    return key, config["base_url"], config["model"]

def format_currency(value, currency_code="BRL"):
    if not value: return "0,00"

    # Mapa de símbolos
    symbols = {"BRL": "R$", "USD": "US$", "EUR": "€", "GBP": "£"}
    sym = symbols.get(currency_code, currency_code)

    # Formatação (BRL usa vírgula, USD usa ponto - vamos simplificar usando padrão BR visual)
    if value > 1e12: return f"{sym} {value/1e12:.2f} Tri"
    if value > 1e9: return f"{sym} {value/1e9:.2f} Bi"
    if value > 1e6: return f"{sym} {value/1e6:.2f} Mi"
    return f"{sym} {value:.2f}"

def annualize_roe(roe_value: float, period: str) -> float:
    """
    Anualiza o ROE se os dados forem YTD (Year-to-Date).
    Ex: Se período é "2025-09-30" (9 meses), multiplica por 12/9.
    """
    if not period or len(period) < 10:
        return roe_value
    try:
        month = int(period[5:7])
        if 0 < month < 12:
            return roe_value * (12 / month)
    except (ValueError, IndexError):
        pass
    return roe_value

# --- UI COMPONENTS (DASHBOARD PROFISSIONAL) ---

# Mapeamento de labels amigaveis para os vereditos
VERDICT_LABELS = {
    AuditVerdict.STRONG_BUY: "COMPRA FORTE",
    AuditVerdict.BUY: "COMPRA",
    AuditVerdict.HOLD: "MANTER",
    AuditVerdict.SELL: "VENDA",
    AuditVerdict.STRONG_SELL: "VENDA FORTE",
    AuditVerdict.SPECULATIVE: "ESPECULATIVO"
}

# Mapeamento de cores para vereditos
VERDICT_COLORS = {
    AuditVerdict.STRONG_BUY: "green",
    AuditVerdict.BUY: "green",
    AuditVerdict.HOLD: "yellow",
    AuditVerdict.SELL: "red",
    AuditVerdict.STRONG_SELL: "red",
    AuditVerdict.SPECULATIVE: "purple"
}

# === TOOLTIPS EDUCATIVOS (Progressive Disclosure) ===
METRIC_TOOLTIPS = {
    "z_score": "Mede a probabilidade de falência em 2 anos. Acima de 2.6 = Seguro. Entre 1.1 e 2.6 = Grey Zone (alerta). Abaixo de 1.1 = Risco alto.",
    "roe": "Retorno sobre o Patrimonio. Quanto a empresa gera de lucro para cada R$1 investido pelos socios.",
    "leverage": "Quantas vezes a empresa esta alavancada. Valores muito altos indicam divida excessiva.",
    "net_margin": "Percentual do faturamento que sobra como lucro liquido apos todas as despesas.",
    "basel": "Indice de Basileia: Reserva de capital do banco. Minimo regulatorio e 8%. Acima de 11% e saudavel.",
    "npl": "Inadimplencia: Percentual de emprestimos em atraso. Abaixo de 3% e excelente.",
    "loss_ratio": "Sinistralidade: Quanto a seguradora paga em sinistros vs. premios recebidos. Abaixo de 65% e bom.",
    "combined": "Indice Combinado: Soma de despesas + sinistros. Abaixo de 100% = lucro operacional.",
    "trust_score": "Nota de 0 a 100 sobre a credibilidade da gestao, baseada na consistencia entre discurso e numeros.",
    "piotroski": "F-Score de Piotroski (0-9 pontos). Avalia força financeira: 8-9 = Forte, 5-7 = Neutra, 0-4 = Fraca."
}

# === TRADUCAO DE TERMOS TECNICOS (Humanizacao) ===
FRIENDLY_LABELS = {
    "z_score": "Risco de Quebra",
    "roe": "Rentabilidade",
    "leverage": "Endividamento",
    "net_margin": "Lucro Real",
    "basel": "Solidez",
    "npl": "Calotes",
    "loss_ratio": "Sinistros",
    "combined": "Eficiencia",
    "trust_score": "Confianca",
    "piotroski": "Força Financeira"
}

# Mapeamento de icones SVG por metrica
METRIC_ICONS = {
    "z_score": "activity",
    "roe": "trending_up",
    "leverage": "scale",
    "net_margin": "dollar",
    "basel": "bank",
    "npl": "alert_triangle",
    "loss_ratio": "umbrella",
    "combined": "bar_chart"
}


def render_titan_dashboard(financials, math_report, audit_report):
    """
    Dashboard profissional com Design System SaaS B2B.
    Progressive Disclosure: Simples primeiro, complexo a um clique.
    """

    # Detecta o setor
    sector = getattr(financials, 'sector', 'Corporate')

    # Cor do veredito
    verdict_color = VERDICT_COLORS.get(audit_report.verdict, "blue")
    verdict_text = VERDICT_LABELS.get(audit_report.verdict, "ANALISE")

    # =========================================================================
    # NIVEL 1: CABECALHO E VEREDITO (Sempre visivel)
    # =========================================================================
    page_header(financials.company_name, financials.period, sector)

    verdict_hero(
        verdict_text=verdict_text,
        color=verdict_color,
        trust_score=audit_report.management_trust_score,
        headline=clean_text(audit_report.headline),
        summary=clean_text(audit_report.executive_summary)
    )
    
    # Botão de copiar análise
    copy_text = f"""# Análise Titan: {financials.company_name}
**Período:** {financials.period}
**Setor:** {sector}
**Veredicto:** {verdict_text}
**Confiança na Gestão:** {audit_report.management_trust_score}/100

## {audit_report.headline}

{audit_report.executive_summary}

### Tese Bull (Otimista)
{chr(10).join(['- ' + item for item in audit_report.bull_case])}

### Tese Bear (Pessimista)
{chr(10).join(['- ' + item for item in audit_report.bear_case])}

### Análise Quantitativa
{audit_report.math_explanation}

---
*Gerado por Titan Auditor em {financials.period}*
"""
    
    # Opções de exportar análise
    with st.expander("📋 Exportar Análise", expanded=False):
        tab_copy, tab_download = st.tabs(["Copiar Texto", "Download MD"])
        
        with tab_copy:
            st.caption("Selecione e copie (Ctrl+C):")
            st.code(copy_text, language="markdown")
        
        with tab_download:
            st.download_button(
                label="⬇️ Baixar arquivo .md",
                data=copy_text,
                file_name=f"titan_{financials.company_name}_{financials.period}.md",
                mime="text/markdown",
                help="Baixar análise como arquivo Markdown"
            )

    # =========================================================================
    # NIVEIS 2, 3, 4: ABAS (Progressive Disclosure)
    # =========================================================================
    tab_resumo, tab_argumentos, tab_tecnico, tab_auditoria = st.tabs([
        "📊 Resumo de Saúde",
        "⚖️ Prós e Contras",
        "📄 Dados Técnicos",
        "🔍 Auditar Cálculos"
    ])

    # -------------------------------------------------------------------------
    # ABA 1: RESUMO DE SAUDE (Metricas com cards profissionais)
    # -------------------------------------------------------------------------
    with tab_resumo:
        section_header("Indicadores-Chave", "bar_chart")

        # === DASHBOARD BANKING ===
        if sector == "Banking":
            m1, m2, m3, m4 = st.columns(4)

            # Card 1: Solidez (Capital/Ativos ou Basileia)
            with m1:
                basel = getattr(financials, 'basel_ratio', None)
                if basel is None:
                    basel = math_report.dupont_analysis.get('capital_ratio', 0)

                # Para bancos: 8%+ é bom, 5-8% é ok, <5% é ruim
                if basel and basel >= 0.08:
                    delta_text = "Sólido"
                    delta_type = "positive"
                elif basel and basel >= 0.05:
                    delta_text = "Adequado"
                    delta_type = "neutral"
                else:
                    delta_text = "Frágil"
                    delta_type = "negative"

                metric_card(
                    label=FRIENDLY_LABELS['basel'],
                    value=f"{basel*100:.1f}%" if basel else "N/A",
                    delta=delta_text if basel else None,
                    delta_type=delta_type if basel else "neutral",
                    icon_name="bank",
                    tooltip="Capital próprio / Ativos totais. Bancos operam com 5-10% tipicamente. >8% é sólido."
                )

            # Card 2: Cobertura de Crédito (PDD/Carteira)
            # NOTA: Isso é COBERTURA de provisão, não inadimplência real
            # 4-6% é normal para bancos brasileiros
            with m2:
                npl = getattr(financials, 'non_performing_loans', None)
                pdd = getattr(financials, 'pdd_balance', None) or 0
                carteira = getattr(financials, 'loan_portfolio', None) or 0

                if npl is not None and npl > 0:
                    # PDD/Carteira - indica cobertura de provisão
                    if npl <= 0.03:
                        delta_text = "Baixa"  # Pode ser sub-provisionamento
                        delta_type = "neutral"
                    elif npl <= 0.06:
                        delta_text = "Saudável"  # Provisão adequada
                        delta_type = "positive"
                    elif npl <= 0.10:
                        delta_text = "Elevada"  # Carteira estressada
                        delta_type = "neutral"
                    else:
                        delta_text = "Crítica"
                        delta_type = "negative"
                    value_text = f"{npl*100:.1f}%"
                    if pdd > 0 and carteira > 0:
                        tooltip_text = f"Cobertura de PDD: R$ {pdd/1e9:.1f}bi provisionados sobre carteira de R$ {carteira/1e9:.0f}bi. Entre 4-6% é considerado saudável para bancos brasileiros."
                    else:
                        tooltip_text = f"Índice de cobertura de {npl*100:.1f}%. 4-6% é saudável, <3% pode indicar sub-provisionamento, >8% indica carteira estressada."
                else:
                    delta_text = "Sem dados"
                    delta_type = "neutral"
                    value_text = "N/A"
                    tooltip_text = "Dados de PDD/Carteira de Crédito não disponíveis neste relatório."

                metric_card(
                    label="PDD/Carteira",
                    value=value_text,
                    delta=delta_text,
                    delta_type=delta_type,
                    icon_name="shield",  # Ícone de proteção, não alerta
                    tooltip=tooltip_text
                )

            # Card 3: Rentabilidade (ROE anualizado)
            with m3:
                roe_raw = math_report.dupont_analysis['roe']
                roe_display = annualize_roe(roe_raw, financials.period)

                # Para bancos: >15% é ótimo, 10-15% é bom, <10% é fraco
                if roe_display >= 15:
                    delta_text = "Excelente"
                    delta_type = "positive"
                elif roe_display >= 10:
                    delta_text = "Bom"
                    delta_type = "positive"
                elif roe_display >= 5:
                    delta_text = "Mediano"
                    delta_type = "neutral"
                else:
                    delta_text = "Fraco"
                    delta_type = "negative"

                # Indica se foi anualizado
                is_annualized = roe_display != roe_raw

                metric_card(
                    label=FRIENDLY_LABELS['roe'],
                    value=f"{roe_display:.1f}%",
                    delta=f"{delta_text}" + (" (anual.)" if is_annualized else ""),
                    delta_type=delta_type,
                    icon_name="trending_up",
                    tooltip=f"Retorno sobre Patrimônio Líquido. Mede lucro gerado sobre capital dos acionistas. Bancos bons: >15%."
                )

            # Card 4: Alavancagem
            with m4:
                leverage = math_report.dupont_analysis['financial_leverage']

                # Para bancos: 8-15x é normal, >15x é alto, <8x é conservador
                if leverage <= 10:
                    delta_text = "Conservador"
                    delta_type = "positive"
                elif leverage <= 15:
                    delta_text = "Normal"
                    delta_type = "neutral"
                else:
                    delta_text = "Elevada"
                    delta_type = "negative"

                metric_card(
                    label=FRIENDLY_LABELS['leverage'],
                    value=f"{leverage:.1f}x",
                    delta=delta_text,
                    delta_type=delta_type,
                    icon_name="scale",
                    tooltip=f"Ativos / Patrimônio Líquido. Indica quanto o banco opera com capital de terceiros. 10-15x é típico para bancos."
                )

        # === DASHBOARD INSURANCE ===
        elif sector == "Insurance":
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                loss = getattr(financials, 'loss_ratio', None)
                metric_card(
                    label=FRIENDLY_LABELS['loss_ratio'],
                    value=f"{loss*100:.1f}%" if loss else "N/A",
                    delta="Saudavel" if loss and loss <= 0.70 else "Pressionada",
                    delta_type="positive" if loss and loss <= 0.70 else "negative",
                    icon_name="umbrella",
                    tooltip=METRIC_TOOLTIPS["loss_ratio"]
                )
            with m2:
                combined = getattr(financials, 'combined_ratio', None)
                metric_card(
                    label=FRIENDLY_LABELS['combined'],
                    value=f"{combined*100:.1f}%" if combined else "N/A",
                    delta="Lucrativo" if combined and combined < 1.0 else "Prejuizo",
                    delta_type="positive" if combined and combined < 1.0 else "negative",
                    icon_name="bar_chart",
                    tooltip=METRIC_TOOLTIPS["combined"]
                )
            with m3:
                # ROE anualizado para seguradoras (dados YTD)
                roe_raw = math_report.dupont_analysis['roe']
                roe_display = annualize_roe(roe_raw, financials.period)
                metric_card(
                    label=FRIENDLY_LABELS['roe'],
                    value=f"{roe_display:.2f}%",
                    icon_name="trending_up",
                    tooltip=METRIC_TOOLTIPS["roe"] + " (anualizado)" if roe_display != roe_raw else METRIC_TOOLTIPS["roe"]
                )
            with m4:
                metric_card(
                    label=FRIENDLY_LABELS['net_margin'],
                    value=f"{math_report.dupont_analysis['net_margin']}%",
                    icon_name="dollar",
                    tooltip=METRIC_TOOLTIPS["net_margin"]
                )

        # === DASHBOARD CORPORATE (Default) ===
        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                z_delta_type = "positive" if math_report.altman_z_score > 2.6 else "negative" if math_report.altman_z_score < 1.1 else "neutral"
                metric_card(
                    label=FRIENDLY_LABELS['z_score'],
                    value=str(math_report.altman_z_score),
                    delta=math_report.solvency_status,
                    delta_type=z_delta_type,
                    icon_name="activity",
                    tooltip=METRIC_TOOLTIPS["z_score"]
                )
            with m2:
                # ROE anualizado para corporates (dados YTD)
                roe_raw = math_report.dupont_analysis['roe']
                roe_display = annualize_roe(roe_raw, financials.period)
                metric_card(
                    label=FRIENDLY_LABELS['roe'],
                    value=f"{roe_display:.2f}%",
                    icon_name="trending_up",
                    tooltip=METRIC_TOOLTIPS["roe"] + " (anualizado)" if roe_display != roe_raw else METRIC_TOOLTIPS["roe"]
                )
            with m3:
                metric_card(
                    label=FRIENDLY_LABELS['leverage'],
                    value=f"{math_report.dupont_analysis['financial_leverage']:.1f}x",
                    icon_name="scale",
                    tooltip=METRIC_TOOLTIPS["leverage"]
                )
            with m4:
                metric_card(
                    label=FRIENDLY_LABELS['net_margin'],
                    value=f"{math_report.dupont_analysis['net_margin']}%",
                    icon_name="dollar",
                    tooltip=METRIC_TOOLTIPS["net_margin"]
                )

            # === PIOTROSKI F-SCORE (Segunda linha de métricas) ===
            if math_report.piotroski_score:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                section_header("Piotroski F-Score (Forca Financeira)", "bar_chart")

                piotroski = math_report.piotroski_score
                p1, p2, p3, p4 = st.columns(4)

                with p1:
                    # Score total com icone baseado no strength_level
                    score_delta_type = "positive" if piotroski["score"] >= 7 else "negative" if piotroski["score"] <= 4 else "neutral"
                    # Mapeia strength_level para icone
                    strength_icon = "award" if piotroski.get("strength_level") == "strong" else "alert_triangle" if piotroski.get("strength_level") == "weak" else "minus"
                    metric_card(
                        label="F-Score Total",
                        value=f"{piotroski['score']}/9",
                        delta=piotroski["interpretation"].split(" - ")[0],
                        delta_type=score_delta_type,
                        icon_name=strength_icon,
                        tooltip=METRIC_TOOLTIPS["piotroski"]
                    )
                with p2:
                    # Profitability (4 pontos)
                    prof_score = piotroski["categories"]["profitability"]
                    metric_card(
                        label="Rentabilidade",
                        value=f"{prof_score}/4",
                        delta="ROA, Cash Flow, Tendência, Qualidade",
                        delta_type="positive" if prof_score >= 3 else "negative" if prof_score <= 1 else "neutral",
                        icon_name="trending_up",
                        tooltip="4 critérios de rentabilidade: ROA positivo, Cash Flow positivo, ROA melhorando, Lucros de qualidade"
                    )
                with p3:
                    # Leverage/Liquidity (3 pontos)
                    lev_score = piotroski["categories"]["leverage_liquidity"]
                    metric_card(
                        label="Solidez",
                        value=f"{lev_score}/3",
                        delta="Dívida, Liquidez, Diluição",
                        delta_type="positive" if lev_score >= 2 else "negative" if lev_score == 0 else "neutral",
                        icon_name="shield",
                        tooltip="3 critérios de solidez: Baixa alavancagem, Current Ratio > 1, Sem emissão de ações"
                    )
                with p4:
                    # Efficiency (2 pontos)
                    eff_score = piotroski["categories"]["efficiency"]
                    metric_card(
                        label="Eficiência",
                        value=f"{eff_score}/2",
                        delta="EBIT Margin, Giro de Ativos",
                        delta_type="positive" if eff_score == 2 else "negative" if eff_score == 0 else "neutral",
                        icon_name="zap",
                        tooltip="2 critérios de eficiência: EBIT Margin > 10%, Asset Turnover > 0.3"
                    )

        # Flags Forenses (Se houver) - Universal
        if math_report.forensic_flags:
            section_header("Alertas Detectados", "alert_triangle")
            for flag in math_report.forensic_flags:
                alert_box(clean_text(flag), variant="warning")

        # Explicacao Matematica
        section_header("Analise Quantitativa", "cpu")
        st.markdown(f"<p style='color: #94a3b8; font-size: 0.875rem; line-height: 1.6;'>{clean_text(audit_report.math_explanation)}</p>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # ABA 2: PROS E CONTRAS (Bull vs Bear)
    # -------------------------------------------------------------------------
    with tab_argumentos:
        section_header("O Contraditorio", "scale")
        st.markdown("<p style='color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem;'>Argumentos a favor e contra o investimento, baseados nos dados.</p>", unsafe_allow_html=True)

        c_bull, c_bear = st.columns(2)

        with c_bull:
            bull_points = [clean_text(p) for p in audit_report.bull_case]
            argument_card("Tese Bull (Otimista)", bull_points, variant="bull")

        with c_bear:
            bear_points = [clean_text(p) for p in audit_report.bear_case]
            argument_card("Tese Bear (Pessimista)", bear_points, variant="bear")

    # -------------------------------------------------------------------------
    # ABA 3: DADOS TECNICOS (JSON bruto para auditores)
    # -------------------------------------------------------------------------
    with tab_tecnico:
        section_header("Dados Brutos", "file_text")
        st.markdown("<p style='color: #64748b; font-size: 0.875rem; margin-bottom: 1rem;'>Informacoes tecnicas extraidas do documento original.</p>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Dados Financeiros Extraidos**")
            st.json(financials.model_dump(), expanded=False)

        with col2:
            st.markdown("**Relatorio do Motor Matematico**")
            math_data = {
                "altman_z_score": math_report.altman_z_score,
                "solvency_status": math_report.solvency_status,
                "dupont_analysis": math_report.dupont_analysis,
                "forensic_flags": math_report.forensic_flags
            }
            st.json(math_data, expanded=False)

        st.markdown("**Relatorio de Auditoria (LLM)**")
        audit_data = {
            "verdict": audit_report.verdict.value,
            "headline": audit_report.headline,
            "executive_summary": audit_report.executive_summary,
            "management_trust_score": audit_report.management_trust_score,
            "bull_case": audit_report.bull_case,
            "bear_case": audit_report.bear_case,
            "math_explanation": audit_report.math_explanation
        }
        st.json(audit_data, expanded=False)

    # -------------------------------------------------------------------------
    # ABA 4: AUDITAR CÁLCULOS (Debug Mode para verificação)
    # -------------------------------------------------------------------------
    with tab_auditoria:
        section_header("Auditoria dos Cálculos", "search")
        st.markdown("""
        <p style='color: #64748b; font-size: 0.875rem; margin-bottom: 1rem;'>
        Esta aba permite verificar cada passo dos cálculos. Compare os valores brutos com o documento original
        para validar a extração. Cada fórmula é mostrada com seus componentes.
        </p>
        """, unsafe_allow_html=True)

        # Verifica se temos dados de auditoria
        if math_report.audit_debug:
            audit_debug = math_report.audit_debug

            # === SEÇÃO 1: DADOS BRUTOS RECEBIDOS ===
            with st.expander("Dados Brutos Extraídos do Documento", expanded=True):
                st.markdown("**Compare estes valores com o documento original para validar a extração:**")
                raw_data = audit_debug.get("raw_data_received", {})

                # Formata para exibição
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**Identificação:**")
                    st.write(f"- Empresa: `{raw_data.get('company_name', 'N/A')}`")
                    st.write(f"- Período: `{raw_data.get('period', 'N/A')}`")
                    st.write(f"- Setor: `{raw_data.get('sector', 'N/A')}`")
                    st.write(f"- Moeda: `{raw_data.get('currency', 'N/A')}`")

                    # Símbolo de moeda dinâmico
                    curr_symbol = "R$" if raw_data.get('currency') == 'BRL' else "$"

                    st.markdown("**Balanço Patrimonial:**")
                    st.write(f"- Ativo Total: `{curr_symbol} {raw_data.get('total_assets', 0):,.0f}`")
                    st.write(f"- Ativo Circulante: `{curr_symbol} {raw_data.get('current_assets', 0) or 0:,.0f}`")
                    st.write(f"- Passivo Circulante: `{curr_symbol} {raw_data.get('current_liabilities', 0) or 0:,.0f}`")
                    st.write(f"- Passivo Total: `{curr_symbol} {raw_data.get('total_liabilities', 0) or 0:,.0f}`")
                    st.write(f"- Patrimônio Líquido: `{curr_symbol} {raw_data.get('equity', 0):,.0f}`")

                with col_b:
                    st.markdown("**Demonstração de Resultados:**")
                    st.write(f"- Receita: `{curr_symbol} {raw_data.get('revenue', 0):,.0f}`")
                    st.write(f"- Lucro Líquido: `{curr_symbol} {raw_data.get('net_income', 0):,.0f}`")
                    st.write(f"- EBIT: `{curr_symbol} {raw_data.get('ebit', 0) or 0:,.0f}`")
                    st.write(f"- EBITDA: `{curr_symbol} {raw_data.get('ebitda', 0) or 0:,.0f}`")
                    st.write(f"- Lucros Acumulados: `{curr_symbol} {raw_data.get('retained_earnings', 0) or 0:,.0f}`")

                    st.markdown("**Caixa e Dívida:**")
                    st.write(f"- Caixa: `{curr_symbol} {raw_data.get('cash', 0) or 0:,.0f}`")
                    st.write(f"- Dívida LP: `{curr_symbol} {raw_data.get('long_term_debt', 0) or 0:,.0f}`")
                    st.write(f"- Dívida CP: `{curr_symbol} {raw_data.get('short_term_debt', 0) or 0:,.0f}`")

            # === SEÇÃO 2: CÁLCULO DO Z-SCORE ===
            with st.expander("Cálculo do Altman Z-Score (Passo a Passo)", expanded=True):
                z_calc = audit_debug.get("z_score_calculation", {})

                st.markdown(f"**Fórmula:** `{z_calc.get('formula', 'N/A')}`")
                st.markdown("---")

                variables = z_calc.get("variables", {})
                for var_name, var_data in variables.items():
                    st.markdown(f"**{var_name}:**")
                    st.write(f"- Cálculo: `{var_data.get('calculation', 'N/A')}`")
                    st.write(f"- Resultado: `{var_data.get('result', 'N/A')}`")

                st.markdown("---")
                st.markdown(f"**Cálculo Final:** `{z_calc.get('final_calculation', 'N/A')}`")
                st.markdown(f"**Resultado Z-Score:** `{z_calc.get('result', 'N/A')}`")

                st.markdown("**Thresholds de Classificação:**")
                thresholds = z_calc.get("thresholds", {})
                for threshold, meaning in thresholds.items():
                    st.write(f"- {threshold}: {meaning}")

            # === SEÇÃO 3: PIOTROSKI F-SCORE BREAKDOWN ===
            if audit_debug.get("piotroski_breakdown"):
                with st.expander("Piotroski F-Score (9 Critérios Detalhados)", expanded=False):
                    piotroski_bd = audit_debug["piotroski_breakdown"]

                    st.markdown("**Sistema de 9 pontos para avaliar força financeira:**")
                    st.markdown("---")

                    for criterion, details in piotroski_bd.items():
                        status_icon = "✅" if details.get("pass") else "❌"
                        st.markdown(f"**{status_icon} {criterion.replace('_', ' ').title()}:**")
                        st.write(f"- Valor: `{details.get('value', 'N/A')}`")
                        st.write(f"- Fórmula: `{details.get('formula', 'N/A')}`")
                        st.write(f"- Critério: `{details.get('threshold', 'N/A')}`")
                        st.write(f"- Passou: `{details.get('pass', False)}`")
                        st.markdown("---")

            # === SEÇÃO 4: MÉTRICAS COMPLEMENTARES ===
            if audit_debug.get("complementary_metrics"):
                with st.expander("Métricas Complementares", expanded=False):
                    comp_metrics = audit_debug["complementary_metrics"]

                    for metric_name, metric_data in comp_metrics.items():
                        st.markdown(f"**{metric_name.replace('_', ' ').title()}:**")
                        st.write(f"- Valor: `{metric_data.get('value', 'N/A')}`")
                        st.write(f"- Interpretação: `{metric_data.get('interpretation', 'N/A')}`")
                        st.write(f"- Fórmula: `{metric_data.get('formula', 'N/A')}`")
                        st.markdown("---")

            # === SEÇÃO 5: DUPONT ANALYSIS ===
            with st.expander("🔬 Análise DuPont", expanded=False):
                dupont = audit_debug.get("dupont_analysis", {})

                st.markdown("**Decomposição do ROE em 3 componentes:**")
                st.markdown("`ROE = Margem Líquida × Giro do Ativo × Alavancagem Financeira`")
                st.markdown("---")

                st.write(f"- Margem Líquida: `{dupont.get('net_margin', 'N/A')}%`")
                st.write(f"- Giro do Ativo: `{dupont.get('asset_turnover', 'N/A')}`")
                st.write(f"- Alavancagem: `{dupont.get('financial_leverage', 'N/A')}x`")

                # ROE com anualização se dados YTD
                roe_raw = dupont.get('roe', 0)
                roe_annualized = annualize_roe(roe_raw, financials.period)
                if roe_annualized != roe_raw:
                    st.write(f"- **ROE Resultante:** `{roe_raw}%` (YTD) → `{roe_annualized:.2f}%` (anualizado)")
                else:
                    st.write(f"- **ROE Resultante:** `{roe_raw}%`")

            # === NOTA DE VERIFICAÇÃO ===
            st.info(f"**Nota:** {audit_debug.get('verification_note', 'Compare os valores brutos com o documento original para validar a extração.')}")

        else:
            st.warning("Dados de auditoria não disponíveis para este relatório. Execute uma nova análise.")

# --- MAIN CONTROLLER ---

def main():
    # Injeta CSS global no inicio
    inject_css()

    # --- SIDEBAR (NAVEGAÇÃO) ---
    with st.sidebar:
        st.header(f"Titan Terminal", anchor=False)
        st.caption("Intelligence Platform v2.0")

        # Navegação Principal
        market_mode = st.radio(
            "Navegação",
            ["Bolsa 🇧🇷", "Bolsas 🇺🇸 | 🇪🇺", "Fundos & ETFs", "Criptoativos", "Macroeconomia", "Auditoria (Upload)"]
        )

        st.markdown("---")

        st.subheader("Configuração da IA")
        provider = st.selectbox("Motor", list(LLM_PROVIDERS.keys()))

        # Mostra Casos de Teste APENAS no modo de Arquivo
        if market_mode == "Auditoria (Upload)":
            st.markdown("---")
            st.subheader("Casos de Teste")

            EXAMPLES = {
                "NVIDIA Q3_25": "examples/nvidia_q3_25.pdf",
                "Nubank Q3_25": "examples/nubank_q3_25.pdf",
                "Americanas Q3_25": "examples/americanas_q3_25.pdf"
            }

            for name, path in EXAMPLES.items():
                if st.button(name, use_container_width=True):
                    st.session_state.selected_example_path = path
                    st.session_state.selected_example_name = name

    # --- ÁREA PRINCIPAL ---

    # 1. MODO MACROECONOMIA (Dashboard Rápido)
    if market_mode == "Macroeconomia":
        st.title("Panorama Global")
        st.markdown("<p style='color: #64748b; font-size: 0.875rem;'>Monitoramento em tempo real dos principais indicadores econômicos.</p>", unsafe_allow_html=True)

        # Cria abas para não poluir
        t1, t2, t3 = st.tabs(["Índices Mundiais", "Commodities", "Câmbio"])

        with t1:
            # Itera sobre o dicionário e cria cards
            cols = st.columns(len(MACRO_ASSETS["indices"]))
            for idx, (name, ticker) in enumerate(MACRO_ASSETS["indices"].items()):
                with st.spinner(f"Carregando {name}..."):
                    info = MarketDataService.get_ticker_info(ticker, region="US") # Índices usam lógica US (sem sufixo .SA)
                if info:
                    with cols[idx]:
                        metric_card(name, f"{info['price']:.2f}", delta_type="neutral")

        with t2:
            cols = st.columns(len(MACRO_ASSETS["commodities"]))
            for idx, (name, ticker) in enumerate(MACRO_ASSETS["commodities"].items()):
                with st.spinner(f"Carregando {name}..."):
                    info = MarketDataService.get_ticker_info(ticker, region="US")
                if info:
                    with cols[idx]:
                        metric_card(name, f"US$ {info['price']:.2f}", delta_type="neutral")

        with t3:
            cols = st.columns(len(MACRO_ASSETS["currencies"]))
            for idx, (name, ticker) in enumerate(MACRO_ASSETS["currencies"].items()):
                with st.spinner(f"Carregando {name}..."):
                    info = MarketDataService.get_ticker_info(ticker, region="US")
                if info:
                    with cols[idx]:
                        metric_card(name, f"{info['price']:.4f}", delta_type="neutral")

    # 2. MODO FUNDOS & ETFS (Bifurcação)
    elif "Fundos" in market_mode:
        st.title("Fundos & ETFs")
        st.markdown("<p style='color: #64748b; font-size: 0.875rem;'>Selecione a categoria de fundos para análise.</p>", unsafe_allow_html=True)

        tab_fii, tab_etf = st.tabs(["FIIs | ETFs (Brasil)", "ETFs Globais"])

        # --- ABA FIIs ---
        with tab_fii:
            st.subheader("Fundos Imobiliários (B3)")

            # Sugestões FII
            suggestions = POPULAR_TICKERS["FII"]
            cols = st.columns(len(suggestions))
            for i, sug in enumerate(suggestions):
                if cols[i].button(sug, key=f"btn_fii_{sug}", use_container_width=True):
                    st.session_state.ticker_search = {"ticker": sug, "region": "BR"}

            # Busca FII
            c_search, c_btn = st.columns([4, 1])
            with c_search:
                fii_input = st.text_input("Ticker FII", placeholder="Ex: HGLG11, KNIP11...", key="input_fii").upper()
            with c_btn:
                if st.button("Buscar", key="btn_search_fii", type="primary", use_container_width=True):
                    st.session_state.ticker_search = {"ticker": fii_input, "region": "BR"}

        # --- ABA ETFs ---
        with tab_etf:
            st.subheader("ETFs Globais (US/Mundo)")

            # Sugestões ETF
            suggestions = POPULAR_TICKERS.get("GLOBAL_ETF", ["IVV", "QQQ"])
            cols = st.columns(len(suggestions))
            for i, sug in enumerate(suggestions):
                if cols[i].button(sug, key=f"btn_etf_{sug}", use_container_width=True):
                    st.session_state.ticker_search = {"ticker": sug, "region": "US"}

            # Busca ETF
            c_search, c_btn = st.columns([4, 1])
            with c_search:
                etf_input = st.text_input("Ticker ETF", placeholder="Ex: IVV, QQQ, EWZ...", key="input_etf").upper()
            with c_btn:
                if st.button("Buscar", key="btn_search_etf", type="primary", use_container_width=True):
                    st.session_state.ticker_search = {"ticker": etf_input, "region": "US"}

        # --- EXIBIÇÃO DE RESULTADOS (Compartilhada) ---
        if st.session_state.ticker_search:
            search_data = st.session_state.ticker_search

            with st.spinner(f"Buscando dados de {search_data['ticker']}..."):
                market_info = MarketDataService.get_ticker_info(search_data['ticker'], region=search_data['region'])

            if market_info:
                currency = market_info['currency']
                st.markdown("---")
                st.markdown(f"## {market_info['name']}")

                sector_display = f"{market_info['sector']} | {market_info['industry']}"
                if market_info.get('is_etf'):
                    sector_display = f"ETF / FUNDO | {market_info['sector']}"
                st.caption(sector_display)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    metric_card("Preço Atual", format_currency(market_info['price'], currency), delta_type="positive")
                with col2:
                    metric_card("Valor de Mercado", format_currency(market_info['market_cap'], currency), delta_type="neutral")
                with col3:
                    dy = market_info['dividend_yield']
                    val_dy = f"{dy*100:.2f}%" if dy and dy > 0 else "N/A"
                    metric_card("Div. Yield", val_dy, "Yahoo Finance", delta_type="neutral",
                               tooltip="Via Yahoo Finance. Pode não incluir todos os proventos.")
                with col4:
                    vol = market_info.get('volume', 0)
                    metric_card("Volume", format_currency(vol, currency), delta_type="neutral")
                
                st.caption("ℹ️ *Dados de mercado via Yahoo Finance.*")

                st.markdown("### Histórico de Cotação (1 Ano)")
                hist_data = MarketDataService.get_price_history(search_data['ticker'], region=search_data['region'])
                st.line_chart(hist_data, color="#10b981", height=250)
            else:
                st.error(f"Ticker '{search_data['ticker']}' não encontrado.")


    # 3. MODO AUDITORIA (LEGADO)
    elif market_mode == "Auditoria (Upload)":
        st.markdown("<h1 style='font-weight: 700; letter-spacing: -0.02em;'>Titan Financial Auditor</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; font-size: 0.875rem;'>Arquitetura Agentica: OCR → Validacao Pydantic → Calculo Deterministico → Auditoria LLM</p>", unsafe_allow_html=True)

        uploaded = st.file_uploader("Upload PDF (Earnings Release)", type="pdf", key="legacy_uploader")

        # --- FEEDBACK VISUAL DO CASO SELECIONADO ---
        if st.session_state.selected_example_name and not uploaded:
            col_card, col_btn = st.columns([0.92, 0.08])
            with col_card:
                st.markdown(f"""
                <div style="
                    background: rgba(30, 41, 59, 0.5);
                    border: 1px solid rgba(99, 102, 241, 0.2);
                    border-radius: 8px;
                    padding: 1rem;
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                ">
                    <div style="background: rgba(99, 102, 241, 0.1); padding: 0.5rem; border-radius: 6px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.25rem;">Caso de Teste Selecionado</div>
                        <div style="font-size: 1.1rem; font-weight: 600; color: #f8fafc;">{st.session_state.selected_example_name}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_btn:
                st.write("") # Espaçamento vertical para alinhar
                st.write("")
                if st.button("✕", key="remove_selection_btn", help="Remover caso selecionado"):
                    st.session_state.selected_example_path = None
                    st.session_state.selected_example_name = None
                    st.rerun()

        target = None
        if uploaded: target = uploaded
        elif st.session_state.selected_example_path:
            if os.path.exists(st.session_state.selected_example_path):
                target = open(st.session_state.selected_example_path, "rb")

        if target and st.button("Iniciar Auditoria Forense", type="primary", key="legacy_audit_btn"):
            run_audit_pipeline(target, provider)
            if hasattr(target, 'close'): target.close()

    # 4. MODO AÇÕES / CRIPTO (Busca Ativa)
    else:
        # Define o contexto baseado na escolha
        if "🇧🇷" in market_mode:
            region_code = "BR"
            suggestions = POPULAR_TICKERS["BR_STOCK"]
            title_suffix = "Ações Brasil"
        elif "🇺🇸" in market_mode or "🇪🇺" in market_mode:
            region_code = "US"
            suggestions = POPULAR_TICKERS["US_STOCK"]
            title_suffix = "Ações Globais"
        else: # Cripto
            region_code = "CRYPTO"
            suggestions = POPULAR_TICKERS["CRYPTO"]
            title_suffix = "Criptoativos"

        st.markdown(f"<h1 style='font-weight: 700; letter-spacing: -0.02em;'>Titan Market: {title_suffix}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; font-size: 0.875rem;'>Digite o ticker ou selecione um ativo popular.</p>", unsafe_allow_html=True)

        # Barra de Busca com Sugestões (Pills)
        st.write("Em Alta:")
        cols = st.columns(len(suggestions))

        # Cria botões rápidos para os populares
        for i, sug in enumerate(suggestions):
            if cols[i].button(sug, use_container_width=True):
                st.session_state.ticker_search = {"ticker": sug, "region": region_code}
                # Não precisa de rerun se usarmos o session_state direto, mas ajuda a limpar

        # Input de Texto
        c_search, c_btn = st.columns([4, 1])
        with c_search:
            ticker_input = st.text_input(
                "Ticker",
                placeholder="Digite o código (ex: PETR4, AAPL, BTC-USD)...",
                label_visibility="collapsed"
            ).upper()

        with c_btn:
            if st.button("Buscar", type="primary", use_container_width=True):
                st.session_state.ticker_search = {"ticker": ticker_input, "region": region_code}

        # Exibição de Dados de Mercado (Se houver busca)
        if st.session_state.ticker_search:
            search_data = st.session_state.ticker_search

            # Se o usuário mudou de aba, limpa a busca anterior se for de outra região (opcional, mas bom UX)
            # Mas aqui vamos confiar que ele quer ver o que buscou.

            with st.spinner(f"Buscando dados de {search_data['ticker']}..."):
                # Passamos a região para o serviço
                market_info = MarketDataService.get_ticker_info(search_data['ticker'], region=search_data['region'])

            if market_info:
                currency = market_info['currency'] # Captura a moeda (USD ou BRL)

                st.markdown("---")
                # Cabeçalho da Empresa
                st.markdown(f"## {market_info['name']}")

                # Badge inteligente para ETF
                sector_display = f"{market_info['sector']} | {market_info['industry']}"
                if market_info.get('is_etf'):
                    sector_display = f"ETF / FUNDO DE ÍNDICE | {market_info['sector']}"

                st.caption(sector_display)

                # Cards de Cotação (Estilo Status Invest)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    metric_card("Preço Atual", format_currency(market_info['price'], currency), delta_type="positive")
                with col2:
                    metric_card("Valor de Mercado", format_currency(market_info['market_cap'], currency), delta_type="neutral")

                # Lógica Condicional de Cards (Crypto vs Stocks)
                if search_data['region'] == 'CRYPTO':
                    with col3:
                        vol = market_info.get('volume', 0)
                        metric_card("Volume (24h)", format_currency(vol, currency), delta_type="neutral")
                    with col4:
                        high = market_info.get('high_24h', 0)
                        low = market_info.get('low_24h', 0)
                        # Formatação simples para range
                        metric_card("Range 24h", f"{low} - {high}", "Min - Max", delta_type="neutral")
                else:
                    with col3:
                        pe = market_info['pe_ratio']
                        pe_val = f"{pe:.2f}x" if pe and pe > 0 else "N/A"
                        metric_card("P/L", pe_val, "Yahoo Finance", delta_type="neutral", 
                                   tooltip="Preço/Lucro via Yahoo Finance. Pode divergir de outras fontes.")
                    with col4:
                        dy = market_info['dividend_yield']
                        val_dy = f"{dy*100:.2f}%" if dy and dy > 0 else "N/A"
                        metric_card("Div. Yield", val_dy, "Yahoo Finance", delta_type="neutral",
                                   tooltip="Dividend Yield via Yahoo Finance. Pode não incluir todos os proventos (JCP, extras).")
                
                # Nota sobre fonte de dados
                st.caption("ℹ️ *Dados de mercado via Yahoo Finance. Para valores precisos de proventos, consulte B3 ou Status Invest.*")

                # Gráfico de Preço (Linha Simples e Elegante)
                st.markdown("### Histórico de Cotação (1 Ano)")
                hist_data = MarketDataService.get_price_history(search_data['ticker'], region=search_data['region'])
                st.line_chart(hist_data, color="#10b981", height=250)

                # A PONTE PARA O TITAN AUDITOR (COM BUSCA AUTOMÁTICA)
                st.markdown("---")
                st.subheader("Auditoria Fundamentalista (IA)")

                # Tenta buscar documento automaticamente
                with st.spinner("Buscando documentos oficiais..."):
                    doc_result = titan_router.fetch_audit_data(search_data['ticker'], search_data['region'])

                # CRYPTO: Auditoria baseada em dados on-chain (sem PDF)
                if doc_result.asset_type == AssetType.CRYPTO:
                    if doc_result.success and doc_result.metadata:
                        audit_data = doc_result.metadata.get("audit_data", {})

                        st.success("Dados on-chain obtidos via CoinGecko.")

                        # Métricas Cripto
                        st.markdown("#### Análise On-Chain")

                        scores = audit_data.get("scores", {})
                        dev_data = audit_data.get("developer_data", {})
                        community = audit_data.get("community_data", {})
                        supply = audit_data.get("supply", {})

                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            cg_score = scores.get("coingecko_score", 0)
                            metric_card("Score Geral", f"{cg_score:.1f}/100" if cg_score else "N/A", delta_type="positive" if cg_score and cg_score > 50 else "neutral")
                        with c2:
                            dev_score = scores.get("developer_score", 0)
                            metric_card("Atividade Dev", f"{dev_score:.1f}/100" if dev_score else "N/A", delta_type="positive" if dev_score and dev_score > 50 else "neutral")
                        with c3:
                            comm_score = scores.get("community_score", 0)
                            metric_card("Comunidade", f"{comm_score:.1f}/100" if comm_score else "N/A", delta_type="positive" if comm_score and comm_score > 50 else "neutral")
                        with c4:
                            liq_score = scores.get("liquidity_score", 0)
                            metric_card("Liquidez", f"{liq_score:.1f}/100" if liq_score else "N/A", delta_type="positive" if liq_score and liq_score > 50 else "neutral")

                        # Tokenomics
                        st.markdown("#### Tokenomics")
                        t1, t2, t3 = st.columns(3)
                        with t1:
                            circ = supply.get("circulating")
                            metric_card("Supply Circulante", f"{circ:,.0f}" if circ else "N/A", delta_type="neutral")
                        with t2:
                            total = supply.get("total")
                            metric_card("Supply Total", f"{total:,.0f}" if total else "∞", delta_type="neutral")
                        with t3:
                            max_s = supply.get("max")
                            metric_card("Supply Máximo", f"{max_s:,.0f}" if max_s else "∞", delta_type="neutral")

                        # Developer Activity
                        if dev_data:
                            st.markdown("#### Atividade de Desenvolvimento")
                            d1, d2, d3 = st.columns(3)
                            with d1:
                                commits = dev_data.get("commit_count_4_weeks", 0)
                                metric_card("Commits (4 sem)", str(commits), delta_type="positive" if commits > 10 else "neutral")
                            with d2:
                                stars = dev_data.get("stars", 0)
                                metric_card("GitHub Stars", f"{stars:,}" if stars else "N/A", delta_type="neutral")
                            with d3:
                                forks = dev_data.get("forks", 0)
                                metric_card("GitHub Forks", f"{forks:,}" if forks else "N/A", delta_type="neutral")

                        # Links úteis
                        links = audit_data.get("links", {})
                        whitepaper = links.get("whitepaper")
                        if whitepaper:
                            st.markdown(f"📄 [Whitepaper Oficial]({whitepaper})")
                    else:
                        st.warning(doc_result.fallback_message or "Não foi possível obter dados on-chain.")

                # STOCKS: Busca documento e oferece fallback
                else:
                    if doc_result.success:
                        # CASO 1: Dados XBRL estruturados (preferencial)
                        if doc_result.document_type == "XBRL":
                            metadata = doc_result.metadata or {}
                            xbrl_data = metadata.get("xbrl_data", {})
                            form_type = metadata.get("form_type", "10-Q")
                            filing_date = metadata.get("filing_date", "")
                            source = metadata.get("source", "SEC XBRL")
                            document_url = metadata.get("document_url", "")
                            
                            # Mensagem com link para documento específico
                            if "CVM" in source:
                                # Para CVM, o document_url deveria ter o arquivo ZIP específico
                                if document_url:
                                    period_link = f"[{form_type} - {filing_date}]({document_url})"
                                else:
                                    # Fallback para portal genérico
                                    cvm_url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
                                    period_link = f"[{form_type} - {filing_date}]({cvm_url})"
                                st.success(f"✅ Dados obtidos via CVM Dados Abertos: {period_link}")
                                button_label = "Auditar com Dados Oficiais CVM"
                            else:
                                # Para SEC, montar link específico do filing
                                if document_url:
                                    period_link = f"[{form_type} - {filing_date}]({document_url})"
                                else:
                                    sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={search_data['ticker']}&type={form_type}&dateb=&owner=include&count=10"
                                    period_link = f"[{form_type} - {filing_date}]({sec_url})"
                                st.success(f"✅ Dados obtidos via SEC EDGAR: {period_link}")
                                button_label = "Auditar com Dados Oficiais SEC"

                            # Mostra preview dos dados extraídos
                            with st.expander("Ver dados brutos extraídos", expanded=False):
                                st.json(xbrl_data)

                            if st.button(button_label, type="primary", key="xbrl_audit_btn"):
                                run_audit_pipeline_from_xbrl(xbrl_data, provider, metadata, search_data['ticker'])

                        # CASO 2: URL de documento HTML (fallback)
                        elif doc_result.document_url:
                            metadata = doc_result.metadata or {}
                            st.success(f"Documento encontrado: [{metadata.get('form_type', 'ITR')}]({doc_result.document_url})")

                            col_auto, col_manual = st.columns(2)
                            with col_auto:
                                if st.button("Auditar Documento Oficial", type="primary", key="auto_audit_btn"):
                                    # Baixa o documento e processa
                                    with st.spinner("Baixando documento da SEC..."):
                                        try:
                                            import requests
                                            from bs4 import BeautifulSoup

                                            headers = {"User-Agent": "TitanAuditor/1.0 (lipearouck@gmail.com)"}
                                            resp = requests.get(doc_result.document_url, headers=headers, timeout=60)

                                            if resp.status_code == 200:
                                                # Se for HTML (SEC), extrai texto limpo
                                                if doc_result.document_type == "HTML":
                                                    soup = BeautifulSoup(resp.text, 'html.parser')

                                                    # Remove scripts e styles
                                                    for script in soup(["script", "style"]):
                                                        script.decompose()

                                                    # Extrai texto
                                                    text = soup.get_text(separator='\n', strip=True)

                                                    # Limpa linhas vazias excessivas
                                                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                                                    clean_text = '\n'.join(lines)

                                                    if len(clean_text) > 500:  # Documento válido
                                                        st.success(f"Documento carregado ({len(clean_text):,} caracteres)")
                                                        run_audit_pipeline_from_text(clean_text, provider, doc_result.metadata or {})
                                                    else:
                                                        st.error("Documento muito curto ou inválido.")
                                                else:
                                                    # PDF - pode processar direto
                                                    from io import BytesIO
                                                    pdf_file = BytesIO(resp.content)
                                                    run_audit_pipeline(pdf_file, provider)
                                            else:
                                                st.error(f"Erro HTTP {resp.status_code} ao baixar documento.")
                                        except ImportError:
                                            st.error("Biblioteca BeautifulSoup não instalada. Execute: pip install beautifulsoup4")
                                        except Exception as e:
                                            st.error(f"Erro ao baixar documento: {str(e)}")

                            with col_manual:
                                st.info("Ou faça upload manual:")
                    else:
                        # Fallback: mostra mensagem e pede upload
                        if doc_result.fallback_message:
                            st.warning(doc_result.fallback_message)
                        else:
                            st.info("Para realizar a auditoria forense do Titan, precisamos do relatório trimestral.")

                    # Upload manual sempre disponível
                    uploaded_file = st.file_uploader(f"Anexar Release de Resultados ({search_data['ticker']})", type="pdf", key="market_uploader")

                    if uploaded_file and st.button("Executar Auditoria Titan", type="primary", key="market_audit_btn"):
                        run_audit_pipeline(uploaded_file, provider)

            else:
                st.error(f"Ticker '{search_data['ticker']}' não encontrado.")

def run_audit_pipeline(target_file, provider_key):
    """
    Executa o pipeline de auditoria completo a partir de um arquivo PDF.
    """
    # 1. Setup de Credenciais e Agentes
    api_key, base_url, model_name = get_api_credentials(provider_key)

    if not api_key or not model_name:
        st.error("Nao foi possivel obter as credenciais da API ou o nome do modelo. Verifique a configuracao.")
        st.stop()

    # Instanciacao dos Modulos do Core
    extractor = TitanExtractor(api_key=api_key, base_url=base_url, model=model_name)
    calculator = TitanMathEngine()
    auditor = TitanAuditor(api_key=api_key, base_url=base_url, model=model_name)

    with st.status("Executando Pipeline Titan...", expanded=True) as status:
        try:
            # --- PASSO 0: OCR ---
            st.write("Lendo documento bruto...")
            raw_text = extract_text_from_pdf(target_file)
            if not raw_text: raise ValueError("PDF Vazio ou ilegivel")

            # Delega para o pipeline de texto
            _run_audit_core(raw_text, extractor, calculator, auditor, status)

        except Exception as e:
            st.error(f"Falha Critica no Pipeline: {str(e)}")
            status.update(label="Abortado", state="error")


def run_audit_pipeline_from_text(raw_text: str, provider_key: str, metadata: dict | None = None):
    """
    Executa o pipeline de auditoria a partir de texto puro (ex: HTML da SEC).
    """
    # 1. Setup de Credenciais e Agentes
    api_key, base_url, model_name = get_api_credentials(provider_key)

    if not api_key or not model_name:
        st.error("Nao foi possivel obter as credenciais da API ou o nome do modelo. Verifique a configuracao.")
        st.stop()

    # Instanciacao dos Modulos do Core
    extractor = TitanExtractor(api_key=api_key, base_url=base_url, model=model_name)
    calculator = TitanMathEngine()
    auditor = TitanAuditor(api_key=api_key, base_url=base_url, model=model_name)

    source_info = ""
    if metadata:
        form_type = metadata.get('form_type', 'Documento')
        filing_date = metadata.get('filing_date', '')
        source = metadata.get('source', '')
        source_info = f" ({form_type} - {source} - {filing_date})"

    with st.status(f"Executando Pipeline Titan{source_info}...", expanded=True) as status:
        try:
            if not raw_text or len(raw_text) < 100:
                raise ValueError("Texto muito curto ou vazio")

            st.write(f"Documento carregado: {len(raw_text):,} caracteres")

            # Delega para o pipeline core
            _run_audit_core(raw_text, extractor, calculator, auditor, status)

        except Exception as e:
            st.error(f"Falha Critica no Pipeline: {str(e)}")
            status.update(label="Abortado", state="error")


def _run_audit_core(raw_text: str, extractor, calculator, auditor, status):
    """
    Core do pipeline de auditoria - compartilhado entre PDF e texto.
    """
    # --- PASSO 1: EXTRACAO ESTRUTURADA ---
    st.write("Agente Extrator: Normalizando dados financeiros (JSON)...")
    financial_data = extractor.extract_from_text(raw_text)
    st.toast(f"Dados extraidos: {financial_data.company_name}")

    # --- PASSO 2: MOTOR MATEMATICO (SEM IA) ---
    st.write("Math Engine: Calculando Z-Score e DuPont Analysis...")
    math_report = calculator.analyze(financial_data)

    # Feedback visual imediato se houver risco (< 1.1 = Zona de Perigo)
    if math_report.altman_z_score < 1.1:
        st.toast(f"ALERTA: Z-Score Crítico ({math_report.altman_z_score}) - Zona de Perigo!")

    # --- PASSO 3: AUDITORIA FINAL ---
    st.write("Agente Auditor: Cruzando Narrativa vs. Realidade Matematica...")
    final_audit = auditor.audit_company(financial_data, math_report, raw_text)

    status.update(label="Auditoria Concluida", state="complete")

    # --- RENDERIZACAO ---
    st.divider()
    render_titan_dashboard(financial_data, math_report, final_audit)


def run_audit_pipeline_from_xbrl(xbrl_data: dict, provider_key: str, metadata: dict, ticker: str):
    """
    Executa o pipeline de auditoria a partir de dados XBRL estruturados.

    Este é o caminho mais confiável - os dados já vêm parseados da API da SEC,
    então não precisamos da LLM para extrair números (apenas para auditar).
    """
    from core.extractor import FinancialStatement

    # 1. Setup de Credenciais
    api_key, base_url, model_name = get_api_credentials(provider_key)

    if not api_key or not model_name:
        st.error("Nao foi possivel obter as credenciais da API ou o nome do modelo.")
        st.stop()

    # Instancia apenas Calculator e Auditor (não precisa do Extractor!)
    calculator = TitanMathEngine()
    auditor = TitanAuditor(api_key=api_key, base_url=base_url, model=model_name)

    form_type = metadata.get('form_type', '10-Q')
    filing_date = metadata.get('filing_date', '')
    source = metadata.get('source', 'SEC')

    # Determina moeda baseada na fonte
    currency = "BRL" if "CVM" in source else "USD"

    # Detecta setor do metadata (Banking ou Corporate)
    detected_sector = metadata.get('sector', 'Corporate')

    with st.status(f"Analisando {ticker} ({form_type} - {filing_date})...", expanded=True) as status:
        try:
            # --- PASSO 1: CONSTRUIR FinancialStatement A PARTIR DO XBRL ---
            st.write("Convertendo dados XBRL para schema interno...")

            # Mapeia campos XBRL para nosso schema
            financial_data = FinancialStatement(
                company_name=ticker,
                period=filing_date or form_type,
                sector=detected_sector,  # Banking ou Corporate (vem do metadata)
                currency=currency,

                # Campos obrigatórios
                total_assets=xbrl_data.get("total_assets", 0),
                equity=xbrl_data.get("equity", 0),
                net_income=xbrl_data.get("net_income", 0),
                revenue=xbrl_data.get("revenue", 0),

                # Campos opcionais (críticos para Z-Score)
                current_assets=xbrl_data.get("current_assets"),
                current_liabilities=xbrl_data.get("current_liabilities"),
                total_liabilities=xbrl_data.get("total_liabilities"),
                retained_earnings=xbrl_data.get("retained_earnings"),
                ebit=xbrl_data.get("ebit"),
                ebitda=xbrl_data.get("ebitda"),
                interest_expense=xbrl_data.get("interest_expense"),

                # Campos de caixa e dívida (para contextualização do Z-Score)
                cash=xbrl_data.get("cash"),
                long_term_debt=xbrl_data.get("long_term_debt"),
                short_term_debt=xbrl_data.get("short_term_debt"),

                # Campos Banking (para IFs)
                basel_ratio=xbrl_data.get("basel_ratio"),
                non_performing_loans=xbrl_data.get("non_performing_loans"),
                deposits=xbrl_data.get("deposits"),
                loan_portfolio=xbrl_data.get("loan_portfolio"),
                pdd_balance=xbrl_data.get("pdd_balance"),
                pdd_expense=xbrl_data.get("pdd_expense"),

                # Campos Insurance (não aplicável para SEC stocks)
                loss_ratio=None,
                combined_ratio=None,
                technical_provisions=None,

                # Outros
                market_cap=None,
            )

            st.toast(f"Dados carregados: {financial_data.company_name}")

            # Mostra resumo dos dados (com símbolo correto da moeda)
            currency_symbol = "R$" if currency == "BRL" else "$"
            st.write(f"Total Assets: {currency_symbol} {financial_data.total_assets:,.0f}")
            st.write(f"Equity: {currency_symbol} {financial_data.equity:,.0f}")
            st.write(f"Net Income: {currency_symbol} {financial_data.net_income:,.0f}")

            # --- PASSO 2: MOTOR MATEMATICO ---
            st.write("Math Engine: Calculando Z-Score e DuPont Analysis...")
            math_report = calculator.analyze(financial_data)

            # Alerta apenas para Zona de Perigo (< 1.1)
            if math_report.altman_z_score < 1.1:
                st.toast(f"ALERTA: Z-Score = {math_report.altman_z_score} - Zona de Perigo!")

            # --- PASSO 3: AUDITORIA COM IA ---
            st.write("Agente Auditor: Gerando análise qualitativa...")

            # Determina se é YTD e quantos meses
            fiscal_months = metadata.get("fiscal_months", 12)
            is_ytd = metadata.get("is_ytd", False)
            ytd_note = f" (YTD {fiscal_months} meses)" if is_ytd else ""

            # Cria contexto narrativo apropriado para a fonte
            if "CVM" in source:
                xbrl_context = f"""
            Dados financeiros oficiais da CVM (Dados Abertos) para {ticker}:

            BALANÇO PATRIMONIAL (posição em {filing_date}):
            - Ativo Total: R$ {xbrl_data.get('total_assets') or 0:,.0f}
            - Ativo Circulante: R$ {xbrl_data.get('current_assets') or 0:,.0f}
            - Passivo Total: R$ {xbrl_data.get('total_liabilities') or 0:,.0f}
            - Passivo Circulante: R$ {xbrl_data.get('current_liabilities') or 0:,.0f}
            - Patrimônio Líquido: R$ {xbrl_data.get('equity') or 0:,.0f}
            - Lucros Acumulados: R$ {xbrl_data.get('retained_earnings') or 0:,.0f}

            DEMONSTRAÇÃO DE RESULTADOS{ytd_note}:
            - Receita Líquida: R$ {xbrl_data.get('revenue') or 0:,.0f}
            - Lucro Líquido: R$ {xbrl_data.get('net_income') or 0:,.0f}
            - EBIT: R$ {xbrl_data.get('ebit') or 0:,.0f}

            CAIXA E DÍVIDA:
            - Caixa e Equivalentes: R$ {xbrl_data.get('cash') or 0:,.0f}
            - Dívida de Longo Prazo: R$ {xbrl_data.get('long_term_debt') or 0:,.0f}

            Período: {form_type} ({filing_date})
            Fonte: CVM Dados Abertos (Portal dados.cvm.gov.br)

            IMPORTANTE: Os valores de DRE são acumulados no ano (YTD de {fiscal_months} meses).
            Para métricas anualizadas, considere multiplicar por {12/fiscal_months:.2f}.
            """
            else:
                xbrl_context = f"""
            Dados financeiros oficiais da SEC (XBRL) para {ticker}:

            BALANCE SHEET:
            - Total Assets: ${xbrl_data.get('total_assets') or 0:,.0f}
            - Current Assets: ${xbrl_data.get('current_assets') or 0:,.0f}
            - Total Liabilities: ${xbrl_data.get('total_liabilities') or 0:,.0f}
            - Current Liabilities: ${xbrl_data.get('current_liabilities') or 0:,.0f}
            - Stockholders Equity: ${xbrl_data.get('equity') or 0:,.0f}
            - Retained Earnings: ${xbrl_data.get('retained_earnings') or 0:,.0f}

            INCOME STATEMENT:
            - Revenue: ${xbrl_data.get('revenue') or 0:,.0f}
            - Net Income: ${xbrl_data.get('net_income') or 0:,.0f}
            - Operating Income (EBIT): ${xbrl_data.get('ebit') or 0:,.0f}

            CASH & DEBT:
            - Cash: ${xbrl_data.get('cash', 0):,.0f}
            - Long Term Debt: ${xbrl_data.get('long_term_debt', 0):,.0f}
            - Short Term Debt: ${xbrl_data.get('short_term_debt', 0):,.0f}

            Período: {form_type} ({filing_date})
            Fonte: SEC EDGAR XBRL API
            """

            final_audit = auditor.audit_company(financial_data, math_report, xbrl_context)

            status.update(label="Auditoria Concluida", state="complete")

            # --- RENDERIZACAO ---
            st.divider()
            render_titan_dashboard(financial_data, math_report, final_audit)

        except Exception as e:
            st.error(f"Falha no Pipeline: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            status.update(label="Abortado", state="error")


if __name__ == "__main__":
    main()
