import json
import logging
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from openai import OpenAI
from prompts import EXTRACTOR_SYSTEM_PROMPT

# Configuração de Logs Profissional
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TitanExtractor")

# --- CONTRATO DE DADOS (SCHEMA) ---
# Isso garante que o Python saiba exatamente o que esperar.
# É o equivalente às Structs do Rust ou Classes do Java.

class FinancialStatement(BaseModel):
    """
    Representação estruturada das demonstrações financeiras.
    Padrão Polymorphic Schema - Suporte Universal a Setores.

    Setores suportados:
    - Banking: Bancos e Fintechs
    - Insurance: Seguradoras
    - Corporate: Empresas Gerais (Varejo, Indústria, Tech)
    """
    # --- IDENTIFICAÇÃO ---
    company_name: str = Field(..., description="Nome legal da empresa identificada")
    period: str = Field(..., description="Período do relatório (ex: 3T24, 2023 Anual)")
    sector: str = Field("Corporate", description="Setor: Banking, Insurance ou Corporate")
    currency: str = Field("BRL", description="Moeda dos valores reportados")

    # --- CAMPOS UNIVERSAIS (OBRIGATÓRIOS) ---
    total_assets: float = Field(..., description="Ativo Total")
    equity: float = Field(..., description="Patrimônio Líquido")
    net_income: float = Field(..., description="Lucro/Prejuízo Líquido")
    revenue: float = Field(..., description="Receita / Margem Financeira / Prêmios (dependendo do setor)")

    # --- CAMPOS CORPORATE (null para Banking/Insurance) ---
    current_assets: Optional[float] = Field(None, description="Ativo Circulante")
    current_liabilities: Optional[float] = Field(None, description="Passivo Circulante")
    total_liabilities: Optional[float] = Field(None, description="Passivo Total")
    retained_earnings: Optional[float] = Field(None, description="Lucros Acumulados")
    ebit: Optional[float] = Field(None, description="EBIT (apenas Corporate)")
    ebitda: Optional[float] = Field(None, description="EBITDA (apenas Corporate)")

    # --- CAMPOS DE CAIXA E DÍVIDA (para contextualização do Z-Score) ---
    cash: Optional[float] = Field(None, description="Caixa e Equivalentes")
    long_term_debt: Optional[float] = Field(None, description="Dívida de Longo Prazo")
    short_term_debt: Optional[float] = Field(None, description="Dívida de Curto Prazo")

    # --- CAMPOS BANKING (null para outros setores) ---
    basel_ratio: Optional[float] = Field(None, description="Índice de Basileia (Bancos)")
    non_performing_loans: Optional[float] = Field(None, description="Índice de Inadimplência/NPL (Bancos)")
    deposits: Optional[float] = Field(None, description="Total de Depósitos (Bancos)")
    loan_portfolio: Optional[float] = Field(None, description="Carteira de Crédito (Bancos)")
    pdd_balance: Optional[float] = Field(None, description="PDD - Provisão para Devedores Duvidosos (saldo)")
    pdd_expense: Optional[float] = Field(None, description="PDD - Despesa de provisão no período")

    # --- CAMPOS INSURANCE (null para outros setores) ---
    loss_ratio: Optional[float] = Field(None, description="Sinistralidade (Seguros) - ex: 0.72 para 72%")
    combined_ratio: Optional[float] = Field(None, description="Índice Combinado (Seguros)")
    technical_provisions: Optional[float] = Field(None, description="Provisões Técnicas (Seguros)")

    # --- CAMPOS OPCIONAIS UNIVERSAIS ---
    market_cap: Optional[float] = Field(None, description="Valor de Mercado")
    interest_expense: Optional[float] = Field(None, description="Despesas Financeiras com Juros")

class ExtractionError(Exception):
    """Exceção customizada para falhas de extração."""
    pass

# --- ENGINE DE EXTRAÇÃO ---

class TitanExtractor:
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "gpt-4o"):
        # Evita passar explicitamente None para parâmetros tipados como `str`.
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = model

    def _get_extraction_prompt(self) -> str:
        return EXTRACTOR_SYSTEM_PROMPT

    def extract_from_text(self, raw_text: str) -> FinancialStatement:
        """
        Orquestra a chamada à LLM e validação via Pydantic.
        """
        logger.info(f"Iniciando extração de dados com modelo {self.model}...")

        # Otimização: Truncar texto excessivo para focar nas tabelas financeiras
        # Num cenário real, usaríamos um classifier para pegar só as páginas de tabelas.
        safe_text = raw_text[:100000]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_extraction_prompt()},
                    {"role": "user", "content": f"EXTRAIA OS DADOS DESTE RELATÓRIO:\n\n{safe_text}"}
                ],
                response_format={"type": "json_object"}
                # Nota: temperature removido para compatibilidade com modelos de reasoning (ex: Grok)
            )

            content = response.choices[0].message.content
            if not content:
                raise ExtractionError("A API retornou um conteúdo vazio.")

            # Validação Profunda (Parsing)
            data_dict = json.loads(content)

            # Aqui acontece a mágica: O Pydantic valida tipos e obrigatoriedade
            statement = FinancialStatement(**data_dict)

            logger.info(f"Extração bem sucedida para: {statement.company_name}")
            return statement

        except json.JSONDecodeError:
            logger.error("Falha ao parsear JSON da LLM.")
            raise ExtractionError("A IA não gerou um JSON válido.")
        except ValidationError as e:
            logger.error(f"Erro de validação de Schema: {e}")
            raise ExtractionError(f"Dados financeiros incompletos ou inválidos: {e}")
        except Exception as e:
            logger.critical(f"Erro crítico na extração: {e}")
            raise ExtractionError(str(e))

