"""HomePulse presentation styles. No model or forecast calculations live here."""
from pathlib import Path
from html import escape

import streamlit as st


MINT = "#67E8C4"
BLUE = "#7DB7FF"
AMBER = "#FFCE87"


def inject_theme():
    css = Path(__file__).with_name("dashboard.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_header():
    st.markdown('''<div class="hp-topbar">
      <div class="hp-brand"><span class="hp-brand-icon" aria-hidden="true">⌁</span>Home<span>Pulse</span></div>
      <div class="hp-topbar-right"><span class="hp-source">U.S. residential electricity</span><span class="hp-pill">Research prototype</span></div>
    </div>
    <div class="hp-hero">
      <div class="hp-hero-copy"><div class="hp-eyebrow">A LITTLE CONTEXT. A CLEARER PICTURE.</div>
        <h1>Your home.<br><span>A new view of energy.</span></h1>
        <p>Explore a monthly electricity estimate for your home profile.<br class="hp-desktop-break"> See the state trends and evidence behind the numbers.</p>
      </div>
      <div class="hp-hero-art" aria-hidden="true">
        <svg viewBox="0 0 360 190" xmlns="http://www.w3.org/2000/svg">
          <defs><linearGradient id="hp-glow" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#67E8C4"/><stop offset="1" stop-color="#7DB7FF"/></linearGradient></defs>
          <g fill="none" stroke="#26394B" stroke-width="1"><ellipse cx="188" cy="153" rx="145" ry="29"/><ellipse cx="188" cy="153" rx="111" ry="20"/><path d="M17 150H349M188 128V185M76 131L300 175M300 131L76 175"/></g>
          <path d="M113 90L181 36L249 90V151H113Z" fill="#15283A" stroke="url(#hp-glow)" stroke-width="2"/>
          <path d="M100 91L181 26L262 91M181 36L226 51L294 104L249 90M249 151L294 128V104" fill="none" stroke="#529FAD" stroke-width="2"/>
          <rect x="130" y="94" width="26" height="27" rx="3" fill="#213D4B" stroke="#67E8C4"/>
          <path d="M143 94V121M130 107H156" stroke="#67E8C4"/>
          <rect x="207" y="94" width="26" height="27" rx="3" fill="#213D4B" stroke="#67E8C4"/>
          <path d="M220 94V121M207 107H233" stroke="#67E8C4"/>
          <path d="M173 151V112H191V151" fill="#31485B" stroke="#7DB7FF"/>
          <circle cx="280" cy="39" r="24" fill="#162E35" stroke="#375C60"/>
          <path d="M284 23L272 41H281L277 55L291 35H282Z" fill="#67E8C4"/>
          <path d="M48 113H65L72 101L81 124L89 113H104M264 74H281L288 63L296 84L303 74H321" fill="none" stroke="url(#hp-glow)" stroke-width="2"/>
          <circle cx="48" cy="113" r="3" fill="#67E8C4"/><circle cx="321" cy="74" r="3" fill="#7DB7FF"/>
        </svg>
      </div>
    </div>''', unsafe_allow_html=True)


def section_label(kicker, title, description=""):
    st.markdown(f'<div class="hp-section"><div class="hp-eyebrow">{escape(kicker)}</div>'
                f'<h3>{escape(title)}</h3><p>{escape(description)}</p></div>', unsafe_allow_html=True)


def dark_home_illustration(svg):
    """Recolour the existing original home drawing for the dark result card."""
    for old, new in {"#F3F9F8":"#142838", "#EDF7F5":"#203B4B", "#F1F8F7":"#203B4B",
                     "#DDF2EE":"#264D56", "#007D80":MINT, "#A5DDD8":AMBER,
                     "#142F43":"#7DB7FF", "#B7D7D6":"#426478"}.items():
        svg = svg.replace(old, new)
    return svg


def style_chart(fig):
    """Apply display-only colours to an existing chart, retaining all observations."""
    palette = {"EIA actual": BLUE, "XGBoost prediction": MINT, "XGBoost estimate": MINT,
               "Seasonal-average benchmark": AMBER, "Seasonal benchmark": AMBER,
               "Perfect prediction": AMBER, "State-month prediction": MINT}
    for trace in fig.data:
        if trace.name in palette:
            if trace.type == "scatter":
                trace.line.color = palette[trace.name]
                trace.marker.color = palette[trace.name]
    fig.update_layout(template="plotly_dark", paper_bgcolor="#111D2C", plot_bgcolor="#111D2C",
        font=dict(family="Inter, system-ui, sans-serif", color="#C3D3E0", size=12),
        title_font=dict(color="#F1F6FB", size=17),
        legend=dict(font=dict(color="#C3D3E0", size=11), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#22374A", bordercolor="#67E8C4", font_color="#F1F6FB"))
    fig.update_xaxes(gridcolor="#233347", zerolinecolor="#31465B", linecolor="#31465B",
                     title_font=dict(color="#A9BECE"), tickfont=dict(color="#A9BECE"))
    fig.update_yaxes(gridcolor="#233347", zerolinecolor="#31465B", linecolor="#31465B",
                     title_font=dict(color="#A9BECE"), tickfont=dict(color="#A9BECE"))
    return fig
