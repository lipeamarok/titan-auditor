import json
import logging
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from openai import OpenAI
from prompts import AUDITOR_SYSTEM_PROMPT

# Importando os schemas dos módulos anteriores para tipagem forte
from .extractor import FinancialStatement
from .calculator import FinancialHealthReport

# Configuração de Logs
logger = logging.getLogger("TitanAuditor")

# --- ESTRUTURAS DE DECISÃO (Enums & Models) ---

class AuditVerdict(str, Enum):
    """Veredito categórico para padronização da UI."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    SPECULATIVE = "SPECULATIVE"

class FinalAuditReport(BaseModel):
    """
    O produto final do sistema. É isso que o Frontend vai renderizar.
    """
    headline: str = Field(..., description="Um título jornalístico impactante sobre a situação da empresa.")
    verdict: AuditVerdict = Field(..., description="A decisão final de investimento.")

    executive_summary: str = Field(..., description="Resumo de 2 parágrafos focado na realidade vs narrativa.")

    bull_case: List[str] = Field(..., description="3 argumentos para quem está otimista (Advogado do Diabo).")
    bear_case: List[str] = Field(..., description="3 argumentos para quem está pessimista (Realidade Dura).")

    # O "Killer Feature": A IA explica por que a matemática (Z-Score) deu aquele resultado
    math_explanation: str = Field(..., description="Explicação qualitativa dos indicadores quantitativos calculados.")

    management_trust_score: int = Field(..., description="Nota de 0 a 100 sobre a credibilidade do discurso da gestão baseada nos dados.", ge=0, le=100)

# --- O ORQUESTRADOR (A IA JUIZ) ---

class TitanAuditor:
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "gpt-4o"):
        # Evita passar explicitamente None para parâmetros tipados como `str`.
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = model

    def _build_system_prompt(self) -> str:
        return AUDITOR_SYSTEM_PROMPT

    def audit_company(self,
                      financials: FinancialStatement,
                      math_report: FinancialHealthReport,
                      raw_text_summary: str) -> FinalAuditReport:
        """
        Funde a análise quantitativa (MathEngine) com a qualitativa (LLM) para gerar o relatório final.
        """
        logger.info(f"Iniciando auditoria final para {financials.company_name}...")

        # Construção do Contexto Rico (Prompt Engineering Avançado)
        # Aqui injetamos a "Verdade Matemática" antes da IA começar a "pensar".

        user_context = f"""
        --- DADOS DA EMPRESA ---
        Nome: {financials.company_name}
        Período: {financials.period}

        --- A VERDADE MATEMÁTICA (Calculada via Code) ---
        Altman Z-Score: {math_report.altman_z_score} ({math_report.solvency_status})
        ROE (DuPont): {math_report.dupont_analysis['roe']}%
        Alavancagem: {math_report.dupont_analysis['financial_leverage']}x
        Flags Forenses Detectadas pelo Python: {json.dumps(math_report.forensic_flags, indent=2)}

        --- CONTEXTO NARRATIVO (Trecho do documento) ---
        {raw_text_summary[:15000]}

        --- INSTRUÇÃO ---
        Com base APENAS nos dados acima, gere o Dossiê Final.
        Se o 'management_trust_score' for baixo, explique o porquê na seção 'executive_summary'.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": user_context}
                ],
                response_format={"type": "json_object"}
                # Nota: temperature removido para compatibilidade com modelos de reasoning (ex: Grok)
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Resposta vazia da IA.")

            # Parsing e Validação Pydantic
            data_dict = json.loads(content)
            report = FinalAuditReport(**data_dict)

            logger.info("Auditoria final concluída com sucesso.")
            return report

        except json.JSONDecodeError:
            logger.error("Erro ao decodificar JSON do Auditor.")
            # Fallback de emergência poderia ser implementado aqui
            raise
        except Exception as e:
            logger.critical(f"Erro crítico no Auditor: {e}")
            raise