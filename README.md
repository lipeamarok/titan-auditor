# 🛡️ Titan Financial Auditor

> **Sistema de Auditoria Financeira Automatizada com IA**
> Análise forense de demonstrações financeiras via fontes oficiais (SEC EDGAR, CVM Dados Abertos)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-red.svg)](https://streamlit.io/)
[![AI](https://img.shields.io/badge/AI-Grok%20%7C%20GPT--5-orange)](https://x.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Índice

- [O Problema](#-o-problema)
- [A Solução](#-a-solução)
- [Arquitetura](#-arquitetura)
- [Fontes de Dados](#-fontes-de-dados)
- [Indicadores Calculados](#-indicadores-calculados)
- [Quick Start](#-quick-start)
- [Uso](#-uso)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Roadmap](#-roadmap)

---

## 💡 O Problema

Investidores enfrentam desafios críticos ao analisar empresas:

1. **Dados fragmentados**: Informações espalhadas entre CVM, SEC, Yahoo Finance
2. **Cálculos complexos**: Z-Score, Piotroski, DuPont exigem conhecimento técnico
3. **Viés narrativo**: Relatórios corporativos escondem riscos em linguagem otimista
4. **Tempo**: Análise manual de um balanço leva horas

## 🚀 A Solução

O **Titan Auditor** automatiza a auditoria financeira em 3 camadas:

```
┌─────────────────────────────────────────────────────────────────┐
│                    TITAN FINANCIAL AUDITOR                       │
├─────────────────────────────────────────────────────────────────┤
│  [1] ROUTER         →  Detecta tipo de ativo e fonte de dados   │
│  [2] EXTRACTOR      →  Extrai dados estruturados via LLM        │
│  [3] MATH ENGINE    →  Calcula indicadores determinísticos      │
│  [4] AUDITOR (LLM)  →  Gera dossiê confrontando narrativa vs    │
│                        matemática                                │
└─────────────────────────────────────────────────────────────────┘
```

### Diferenciais

- ✅ **Multi-região**: Suporte a Brasil (B3) e EUA (NYSE/NASDAQ)
- ✅ **Dados oficiais**: Extração direta de SEC EDGAR (XBRL) e CVM Dados Abertos
- ✅ **Transparência total**: Aba "Auditar Cálculos" mostra cada fórmula passo-a-passo
- ✅ **Análise setorial**: Estratégias diferentes para Bancos, Seguradoras e Corporações
- ✅ **LLM como juiz**: IA confronta narrativa do management com realidade matemática

---

## 🏗️ Arquitetura

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Streamlit  │────▶│   Router    │────▶│  SEC EDGAR   │
│   (Frontend) │     │  (Decisor)  │     │  (US Stocks) │
└──────────────┘     └─────────────┘     └──────────────┘
       │                   │                    │
       │                   ▼                    │
       │            ┌─────────────┐             │
       │            │  CVM Dados  │             │
       │            │  Abertos    │             │
       │            │ (BR Stocks) │             │
       │            └─────────────┘             │
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EXTRACTOR (LLM)                                │
│           Transforma PDF/XBRL → JSON estruturado                  │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MATH ENGINE                                    │
│    Z-Score │ Piotroski │ DuPont │ Basileia │ etc                 │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AUDITOR (LLM)                                  │
│         Gera dossiê: Narrativa vs Realidade                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 Fontes de Dados

| Região | Fonte | Tipo de Dado | Formato |
|--------|-------|--------------|---------|
| 🇧🇷 Brasil | CVM Dados Abertos | ITR/DFP Trimestrais | CSV (dentro de ZIP) |
| 🇺🇸 EUA | SEC EDGAR | 10-Q/10-K Filings | XBRL (JSON API) |
| 🌐 Crypto | CoinGecko | Market Data | REST API |

### Empresas Brasileiras Suportadas

O sistema mapeia automaticamente tickers B3 para nomes CVM:

```
PETR4  → PETROLEO BRASILEIRO S.A. - PETROBRAS
VALE3  → VALE S.A.
ITUB4  → ITAU UNIBANCO HOLDING S.A.
BBDC4  → BANCO BRADESCO S.A.
MGLU3  → MAGAZINE LUIZA S.A.
AMER3  → AMERICANAS S.A.
WEGE3  → WEG S.A.
B3SA3  → B3 S.A. - BRASIL, BOLSA, BALCAO
RENT3  → LOCALIZA RENT A CAR S.A.
RADL3  → RAIA DROGASIL S.A.
... (25+ empresas mapeadas)
```

### Schema de Dados Unificado

```python
FinancialStatement:
  # Identificação
  - company_name, period, sector, currency

  # Balanço Patrimonial
  - total_assets, equity, current_assets, current_liabilities
  - total_liabilities, retained_earnings

  # DRE (Demonstração de Resultados)
  - revenue, net_income, ebit, ebitda

  # Caixa e Dívida
  - cash, long_term_debt, short_term_debt

  # Banking (opcional)
  - basel_ratio, non_performing_loans, deposits, loan_portfolio

  # Insurance (opcional)
  - loss_ratio, combined_ratio, technical_provisions
```

---

## 📈 Indicadores Calculados

### 1. Altman Z-Score (Risco de Falência)

**Fórmula (Corporate - Mercados Emergentes):**
```
Z = 6.56×X1 + 3.26×X2 + 6.72×X3 + 1.05×X4

Onde:
  X1 = Working Capital / Total Assets
  X2 = Retained Earnings / Total Assets
  X3 = EBIT / Total Assets
  X4 = Equity / Total Liabilities
```

**Thresholds de Classificação:**

| Score | Status | Interpretação |
|-------|--------|---------------|
| > 2.6 | 🟢 Zona Segura | Baixo risco de insolvência |
| 1.1 - 2.6 | 🟡 Grey Zone | Requer monitoramento |
| < 1.1 | 🔴 Zona de Perigo | Alto risco de falência |

### 2. Piotroski F-Score (Força Financeira)

Sistema de 9 pontos avaliando três dimensões:

| Categoria | Critérios | Pontos |
|-----------|-----------|--------|
| **Rentabilidade** | ROA > 0, Cash Flow > 0, ROA Trend > 3%, Qualidade (EBITDA > Net Income) | 4 |
| **Solidez** | Alavancagem < 50%, Current Ratio > 1, Sem diluição | 3 |
| **Eficiência** | EBIT Margin > 10%, Asset Turnover > 0.3 | 2 |

**Interpretação:**

| Score | Classificação | Recomendação |
|-------|---------------|--------------|
| 7-9 | 🟢 FORTE | Fundamentos sólidos |
| 4-6 | 🟡 NEUTRA | Avaliar contexto |
| 0-3 | 🔴 FRACA | Sinais de alerta |

### 3. Análise DuPont (Decomposição do ROE)

```
ROE = Margem Líquida × Giro do Ativo × Alavancagem Financeira
    = (Net Income/Revenue) × (Revenue/Assets) × (Assets/Equity)
```

### 4. Indicadores Setoriais

**Banking (Bancos):**
- Índice de Basileia (Capital Adequacy) - mínimo 11%
- NPL (Non-Performing Loans) - inadimplência
- ROE Bancário ajustado

**Insurance (Seguradoras):**
- Sinistralidade (Loss Ratio)
- Índice Combinado < 100%
- Provisões Técnicas

---

## ⚡ Quick Start

### Pré-requisitos

- Python 3.10+
- Chave de API: OpenAI ou xAI (Grok)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/titan-auditor.git
cd titan-auditor

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt
```

### Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
# OpenAI (GPT-4/5)
OPENAI_API_KEY=sk-...

# xAI (Grok) - opcional
XAI_API_KEY=xai-...
```

### Execução

```bash
streamlit run app.py
```

Acesse: `http://localhost:8501`

---

## 🎯 Uso

### Busca por Ticker

Digite o ticker na barra de busca:

| Mercado | Exemplos |
|---------|----------|
| 🇧🇷 Brasil (B3) | `PETR4`, `VALE3`, `ITUB4`, `MGLU3`, `AMER3` |
| 🇺🇸 EUA (NYSE/NASDAQ) | `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `TSLA` |

O sistema automaticamente:
1. Identifica a região (BR/US) pelo padrão do ticker
2. Busca documento oficial (CVM/SEC)
3. Extrai dados estruturados via LLM
4. Calcula todos os indicadores
5. Gera dossiê de auditoria

### Upload de PDF

Também aceita upload direto de:
- Earnings Releases
- Relatórios Trimestrais (ITR/DFP)
- 10-K / 10-Q filings

### Interpretação do Dossiê

| Seção | Descrição |
|-------|-----------|
| **Veredito** | STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL |
| **Headline** | Título jornalístico sobre a situação |
| **Resumo Executivo** | Narrativa vs Realidade em 2 parágrafos |
| **Gestão (0-100)** | Score de confiança no management |
| **Indicadores-Chave** | Z-Score, ROE, Alavancagem, Margem |
| **Piotroski F-Score** | Breakdown dos 9 critérios |
| **Tese Bull/Bear** | 3 argumentos prós e 3 contras |
| **Auditar Cálculos** | Fórmulas passo-a-passo para validação |

---

## 📁 Estrutura do Projeto

```
titan-auditor/
├── app.py                 # Interface Streamlit principal
├── ui.py                  # Design System (componentes visuais)
├── prompts.py             # System prompts para LLMs
├── requirements.txt       # Dependências Python
├── .env                   # Variáveis de ambiente (não commitado)
│
├── core/
│   ├── router.py          # Roteador inteligente de fontes de dados
│   ├── extractor.py       # Extração de dados via LLM (PDF → JSON)
│   ├── calculator.py      # Motor matemático determinístico
│   ├── auditor.py         # Gerador de dossiê (LLM como Juiz)
│   ├── market_data.py     # Integração Yahoo Finance
│   └── market_map.py      # Mapeamento de tickers e macroativos
│
└── examples/              # PDFs de exemplo para testes
```

### Descrição dos Módulos

| Módulo | Responsabilidade |
|--------|------------------|
| `router.py` | Detecta tipo de ativo, escolhe fonte (CVM/SEC), baixa documentos |
| `extractor.py` | Usa LLM para transformar texto não-estruturado em JSON tipado |
| `calculator.py` | Cálculos 100% determinísticos (Z-Score, Piotroski, DuPont) |
| `auditor.py` | LLM confronta narrativa corporativa com realidade matemática |
| `app.py` | Orquestra o pipeline e renderiza UI no Streamlit |

---

## 🛣️ Roadmap

### ✅ v1.0 (Atual)
- [x] Extração SEC EDGAR via XBRL API
- [x] Extração CVM Dados Abertos (ZIP/CSV)
- [x] Mapeamento ticker → nome CVM (25+ empresas)
- [x] Altman Z-Score (Corporate/Banking)
- [x] Piotroski F-Score (9 critérios)
- [x] Análise DuPont (3 componentes)
- [x] Multi-LLM (Grok, GPT-5, GPT-4.1)
- [x] Aba "Auditar Cálculos" com transparência total
- [x] Suporte a moedas BRL/USD dinâmico
- [x] Detecção de dados YTD (acumulado)

### 🔜 v1.1 (Planejado)
- [ ] Suporte a FIIs (Fundos Imobiliários)
- [ ] Histórico de análises por empresa
- [ ] Comparativo setorial (peer comparison)
- [ ] Exportação PDF do dossiê
- [ ] Cache de documentos baixados

### 🚀 v2.0 (Futuro)
- [ ] API REST para integração externa
- [ ] Alertas automáticos (Z-Score < 1.1)
- [ ] Backtesting de decisões
- [ ] Suporte a mercados europeus
- [ ] Dashboard de portfolio

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

---

## 📜 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## ⚠️ Disclaimer

Este software é fornecido **apenas para fins educacionais e informativos**.

**Não constitui recomendação de investimento.**

Sempre consulte um profissional qualificado antes de tomar decisões financeiras. Os desenvolvedores não se responsabilizam por perdas decorrentes do uso desta ferramenta.

---

<p align="center">
  <strong>Desenvolvido por Felipe Arouck</strong><br>
  <em>Python • IA • Finanças Quantitativas</em>
</p>
