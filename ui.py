# -*- coding: utf-8 -*-
"""
Titan Auditor - Design System
Camada de UI profissional com CSS Injection e componentes SVG.
Estetica SaaS B2B inspirada em Stripe, Vercel e Bloomberg Terminal.
"""

import streamlit as st
from typing import Optional

# =============================================================================
# ICONES SVG (Lucide/Heroicons Style)
# =============================================================================

ICONS = {
    "shield": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',

    "trending_up": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',

    "trending_down": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>',

    "alert_triangle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',

    "check_circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',

    "x_circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',

    "bar_chart": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',

    "activity": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',

    "dollar": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',

    "bank": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M3 10h18"/><path d="M5 6l7-3 7 3"/><path d="M4 10v11"/><path d="M20 10v11"/><path d="M8 14v3"/><path d="M12 14v3"/><path d="M16 14v3"/></svg>',

    "building": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>',

    "umbrella": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M23 12a11.05 11.05 0 0 0-22 0zm-5 7a3 3 0 0 1-6 0v-7"/></svg>',

    "scale": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>',

    "file_text": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',

    "cpu": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
}


# =============================================================================
# CSS GLOBAL (Injecao de Estilo)
# =============================================================================

GLOBAL_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}

.titan-card {
    background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 1.25rem;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 0.5rem;
}

.titan-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}

.titan-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}

.titan-card-icon {
    color: #64748b;
    opacity: 0.8;
}

.titan-card-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #cbd5e1;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.titan-card-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.1;
    margin-bottom: 0.5rem;
}

.has-tooltip {
    cursor: help;
    border-bottom: 1px dotted #94a3b8;
}

.titan-card-delta {
    font-size: 0.8rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}

.delta-positive {
    color: #22c55e;
    background: rgba(34, 197, 94, 0.15);
}

.delta-negative {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.15);
}

.delta-neutral {
    color: #f59e0b;
    background: rgba(245, 158, 11, 0.15);
}

.titan-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.badge-green {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}

.badge-red {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.badge-yellow {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

.badge-purple {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.3);
}

.badge-blue {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.3);
}

.verdict-hero {
    background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
}

.verdict-label {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
}

.verdict-green { color: #22c55e; }
.verdict-red { color: #ef4444; }
.verdict-yellow { color: #f59e0b; }
.verdict-purple { color: #a855f7; }

.titan-alert {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    border-radius: 8px;
    margin: 0.5rem 0;
}

.alert-warning {
    background: rgba(245, 158, 11, 0.1);
    border-left: 3px solid #f59e0b;
    color: #fbbf24;
}

.alert-error {
    background: rgba(239, 68, 68, 0.1);
    border-left: 3px solid #ef4444;
    color: #f87171;
}

.alert-success {
    background: rgba(34, 197, 94, 0.1);
    border-left: 3px solid #22c55e;
    color: #4ade80;
}

.alert-icon {
    flex-shrink: 0;
    margin-top: 2px;
}

.alert-content {
    font-size: 0.875rem;
    line-height: 1.5;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.section-header-icon {
    color: #64748b;
}

.section-header-text {
    font-size: 1.125rem;
    font-weight: 600;
    color: #e2e8f0;
    letter-spacing: -0.01em;
}

.argument-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 1.25rem;
}

.argument-card-bull {
    border-left: 3px solid #22c55e;
}

.argument-card-bear {
    border-left: 3px solid #ef4444;
}

.argument-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}

.argument-title-bull { color: #22c55e; }
.argument-title-bear { color: #ef4444; }

.argument-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    font-size: 0.875rem;
    color: #cbd5e1;
    line-height: 1.5;
}

.argument-bullet-bull { color: #22c55e; }
.argument-bullet-bear { color: #ef4444; }

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    background: rgba(255, 255, 255, 0.08) !important;
}
</style>"""


# =============================================================================
# COMPONENTES UI
# =============================================================================

def inject_css():
    """Injeta o CSS global na pagina."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def icon(name: str, size: int = 24, color: str = "currentColor") -> str:
    """Retorna um icone SVG como string HTML."""
    svg = ICONS.get(name, ICONS["shield"])
    svg = svg.replace('width="24"', f'width="{size}"')
    svg = svg.replace('height="24"', f'height="{size}"')
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    return svg

def metric_card(label: str, value: str, delta: Optional[str] = None, delta_type: str = "neutral", icon_name: str = "bar_chart", tooltip: Optional[str] = None):
    """
    Renderiza um card de metrica profissional.
    Renderiza um card de metrica profissional.

    Args:
        label: Titulo da metrica
        value: Valor principal
        delta: Texto de variacao (opcional)
        delta_type: "positive", "negative" ou "neutral"
        icon_name: Nome do icone SVG
        tooltip: Texto de ajuda (opcional)
    """
    delta_class = f"delta-{delta_type}"
    delta_html = f'<span class="titan-card-delta {delta_class}">{delta}</span>' if delta else ''

    tooltip_attr = f'title="{tooltip}"' if tooltip else ''
    label_class = "titan-card-label has-tooltip" if tooltip else "titan-card-label"

    # HTML sem indentacao para evitar bug do Markdown Code Block
    html = f"""<div class="titan-card" {tooltip_attr}>
<div class="titan-card-header">
<span class="titan-card-icon">{icon(icon_name, size=18)}</span>
<span class="{label_class}">{label}</span>
</div>
<div class="titan-card-value">{value}</div>
{delta_html}
</div>"""
    st.markdown(html, unsafe_allow_html=True)


def badge(text: str, variant: str = "blue") -> str:
    """
    Retorna HTML de uma badge/pill.

    Args:
        text: Texto da badge
        variant: "green", "red", "yellow", "purple", "blue"
    """
    return f'<span class="titan-badge badge-{variant}">{text}</span>'


def verdict_hero(verdict_text: str, color: str, trust_score: int, headline: str, summary: str):
    """
    Renderiza o hero section do veredito.

    Args:
        verdict_text: Texto do veredito (ex: "COMPRA FORTE")
        color: "green", "red", "yellow", "purple"
        trust_score: Score de confianca (0-100)
        headline: Manchete do relatorio
        summary: Resumo executivo
    """
    trust_badge = "green" if trust_score > 70 else "red" if trust_score < 40 else "yellow"
    trust_label = "Confiavel" if trust_score > 70 else "Suspeito" if trust_score < 40 else "Neutro"

    html = f'''<div class="verdict-hero">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
            <div>
                <div class="verdict-label verdict-{color}" style="font-size: 2.5rem;">{verdict_text}</div>
                <div style="margin-top: 0.5rem;">
                    {badge(f"Gestao: {trust_score}/100 - {trust_label}", trust_badge)}
                </div>
            </div>
        </div>
        <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="font-size: 1.25rem; font-weight: 600; color: #f8fafc; margin-bottom: 0.75rem; line-height: 1.4;">"{headline}"</div>
            <div style="font-size: 1rem; color: #cbd5e1; line-height: 1.7;">{summary}</div>
        </div>
    </div>'''
    st.markdown(html, unsafe_allow_html=True)


def section_header(text: str, icon_name: str = "bar_chart"):
    """Renderiza um cabecalho de secao."""
    html = f'''<div class="section-header">
        <span class="section-header-icon">{icon(icon_name, size=20)}</span>
        <span class="section-header-text">{text}</span>
    </div>'''
    st.markdown(html, unsafe_allow_html=True)


def alert_box(message: str, variant: str = "warning"):
    """
    Renderiza um box de alerta.

    Args:
        message: Texto do alerta
        variant: "warning", "error", "success"
    """
    icon_map = {
        "warning": "alert_triangle",
        "error": "x_circle",
        "success": "check_circle"
    }
    html = f'''<div class="titan-alert alert-{variant}">
        <span class="alert-icon">{icon(icon_map.get(variant, "alert_triangle"), size=18)}</span>
        <span class="alert-content">{message}</span>
    </div>'''
    st.markdown(html, unsafe_allow_html=True)


def argument_card(title: str, points: list, variant: str = "bull"):
    """
    Renderiza card de argumentos (Bull ou Bear).

    Args:
        title: Titulo do card
        points: Lista de argumentos
        variant: "bull" ou "bear"
    """
    bullet_icon = "check_circle" if variant == "bull" else "x_circle"
    bullet_color = "#22c55e" if variant == "bull" else "#ef4444"

    points_html = ""
    for point in points:
        points_html += f'''<div class="argument-item">
            <span class="argument-bullet-{variant}">{icon(bullet_icon, size=16, color=bullet_color)}</span>
            <span>{point}</span>
        </div>'''

    html = f'''<div class="argument-card argument-card-{variant}">
        <div class="argument-title argument-title-{variant}">
            {icon("trending_up" if variant == "bull" else "trending_down", size=16, color=bullet_color)}
            {title}
        </div>
        {points_html}
    </div>'''
    st.markdown(html, unsafe_allow_html=True)


def page_header(company_name: str, period: str, sector: str):
    """
    Renderiza o cabecalho da pagina com informacoes da empresa.
    """
    sector_icons = {
        "Banking": "bank",
        "Insurance": "umbrella",
        "Corporate": "building"
    }
    icon_name = sector_icons.get(sector, "building")

    html = f'''<div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;">
        <span style="color: #64748b;">{icon("shield", size=32)}</span>
        <div>
            <h1 style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #f8fafc;">
                Dossie Titan: {company_name}
            </h1>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-top: 0.25rem;">
                {badge(period, "blue")}
                <span style="display: inline-flex; align-items: center; gap: 0.375rem; color: #64748b; font-size: 0.875rem;">
                    {icon(icon_name, size=14)} {sector}
                </span>
            </div>
        </div>
    </div>'''
    st.markdown(html, unsafe_allow_html=True)
