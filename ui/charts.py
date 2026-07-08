from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _layout(theme, height: int, yaxis_title: str, yaxis_range=None):
    layout = dict(
        height=height,
        template=theme.PLOTTEM,
        paper_bgcolor=theme.PLOTBG,
        plot_bgcolor=theme.PLOTBG,
        font=dict(family="Inter", color=theme.TEXT),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=theme.BORDER),
        yaxis=dict(title=yaxis_title, gridcolor=theme.BORDER, title_font=dict(color=theme.SUB), tickfont=dict(color=theme.SUB)),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
    )
    if yaxis_range is not None:
        layout["yaxis"]["range"] = yaxis_range
    return layout


def render_liquidity_chart(data, theme) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color=theme.SUB, width=1.0), opacity=0.7))
    for _, grp in data.groupby((data["Renk10"] != data["Renk10"].shift()).cumsum()):
        fig.add_trace(go.Scatter(x=grp.index, y=grp["SMA10"], mode="lines", line=dict(color=grp["Renk10"].iloc[0], width=1.5, dash="dot"), showlegend=False))
    for _, grp in data.groupby((data["Renk50"] != data["Renk50"].shift()).cumsum()):
        fig.add_trace(go.Scatter(x=grp.index, y=grp["SMA50"], mode="lines", line=dict(color=grp["Renk50"].iloc[0], width=2.5), showlegend=False))
    fig.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyatı", line=dict(color="#F0B90B", width=1.2, dash="dot"), yaxis="y2"))
    for lbl, col, dsh in [("SMA50 Boğa", "#4ADE80", "solid"), ("SMA50 Ayı", "#F87171", "solid"), ("SMA10 Boğa", "#4ADE80", "dot"), ("SMA10 Ayı", "#F87171", "dot")]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=lbl, line=dict(color=col, dash=dsh, width=2)))
    fig.update_layout(**_layout(theme, 540, "Rasyo"))
    fig.update_layout(yaxis2=dict(title="BTC (USD)", overlaying="y", side="right", title_font=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"), gridcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)


def render_portfolio_comparison_chart(data, theme) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="BTC+Altın Rotasyon", line=dict(color="#6FE3B5", width=2.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#E5C07B", width=1.5, dash="dash")))
    fig.update_layout(**_layout(theme, 360, "Portföy Değeri (USD)"))
    st.plotly_chart(fig, use_container_width=True)


def render_allocation_chart(data, theme) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["BtcPct"], name="BTC %", line=dict(color="#F0B90B", width=1.2), fill="tozeroy", fillcolor="rgba(240,185,11,0.15)"))
    fig.add_trace(go.Scatter(x=data.index, y=data["AltinPct"], name="Altın %", line=dict(color="#E5C07B", width=1.2), fill="tozeroy", fillcolor="rgba(229,192,123,0.08)"))
    fig.update_layout(**_layout(theme, 200, "%", [0, 110]))
    fig.update_layout(legend=dict(orientation="h", y=1.08, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)
