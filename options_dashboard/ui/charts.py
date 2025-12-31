import os
import tempfile
import datetime
import webbrowser
import numpy as np
import pandas as pd
import altair as alt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from config import RISK_FREE_RATE, DIVIDEND_YIELD
from models.dealer import find_zero_gamma
from utils.time import time_to_expiration

def build_exposure_dataframe(exposure_rows):
    df = pd.DataFrame(exposure_rows)
    df["Exposure_Bn"] = df["Exposure"] / 1e9
    return df

def generate_altair_chart(
    df_plot,
    symbol,
    expiration,
    model_name,
    spot_price,
    total_exposure,
    zero_gamma=None
):
    min_strike = df_plot["Strike"].min()
    max_strike = df_plot["Strike"].max()

    chart = (
        alt.Chart(df_plot)
        .mark_bar(size=14)
        .encode(
            x=alt.X(
                "Strike:Q",
                title="Strike Price",
                scale=alt.Scale(domain=[min_strike, max_strike])
            ),
            y=alt.Y(
                "Exposure_Bn:Q",
                title=f"{model_name} Exposure (Bn)",
                scale=alt.Scale(domainMid=0)
            ),
            color=alt.Color(
                "Type:N",
                scale=alt.Scale(domain=["CALL", "PUT"], range=["green", "red"])
            )
        )
        .properties(
            title={
                "text": [f"{symbol} {model_name} Exposure ({expiration})"],
                "subtitle": [
                    f"Total {model_name}: {total_exposure:+.2f} Bn | "
                    f"Updated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ],
            },
            width=850,
            height=450
        )
    )

    if zero_gamma:
        zg_df = pd.DataFrame({"Strike": [zero_gamma]})
        zg_line = alt.Chart(zg_df).mark_rule(
            color="purple", strokeDash=[6, 4]
        ).encode(x="Strike:Q")

        chart = chart + zg_line

    return chart

def open_altair_chart(chart, symbol, expiration):
    filename = f"{symbol}_{expiration.replace(':','-')}_exposure.html"
    path = os.path.join(tempfile.gettempdir(), filename)
    chart.save(path)
    webbrowser.open(f"file://{path}")

def compute_bar_width(strikes):
    strikes = sorted(strikes)
    if len(strikes) < 2:
        return 1.0

    spacing = strikes[1] - strikes[0]

    if spacing <= 1:
        return spacing * 0.7
    elif spacing <= 2.5:
        return spacing * 0.55
    elif spacing <= 5:
        return spacing * 0.35
    else:
        return spacing * 0.25


def compute_xticks(strikes):
    strikes = sorted(strikes)
    if len(strikes) < 2:
        return strikes

    spacing = strikes[1] - strikes[0]

    if spacing <= 1:
        interval = 2
    elif spacing <= 2.5:
        interval = 5
    elif spacing <= 5:
        interval = 10
    else:
        interval = spacing * 2

    start = int(strikes[0] // interval) * interval
    end   = int((strikes[-1] + interval) // interval) * interval

    return list(range(start, end + interval, interval))


def embed_matplotlib_chart(
    parent,
    df_plot,
    symbol,
    expiration,
    model_name,
    total_exposure,
    zero_gamma=None
):
    fig = Figure(figsize=(9, 6), dpi=100)
    ax = fig.add_subplot(111)
    calls = df_plot[df_plot["Type"] == "CALL"]
    puts  = df_plot[df_plot["Type"] == "PUT"]
    strikes = sorted(df_plot["Strike"].unique())
    bar_width = compute_bar_width(strikes)

    ax.bar(
        calls["Strike"],
        calls["Exposure_Bn"],
        width=bar_width,
        color="#2ECC71",
        edgecolor="black",
        linewidth=0.6,
        label="CALL"
    )

    ax.bar(
        puts["Strike"],
        puts["Exposure_Bn"],
        width=bar_width,
        color="#E74C3C",
        edgecolor="black",
        linewidth=0.6,
        label="PUT"
    )

    ax.axhline(0, color="black", linewidth=1)

    if zero_gamma:
        ax.axvline(
            zero_gamma,
            color="purple",
            linestyle="--",
            linewidth=1.5,
            label="Dealer Flip"
        )

    ax.set_title(
        f"{symbol} {model_name} Exposure ({expiration})",
        fontsize=14
    )
    ax.set_xlabel("Strike Price", fontsize=12)
    ax.set_ylabel(f"{model_name} Exposure (Bn)", fontsize=12)
    xticks = compute_xticks(strikes)
    ax.set_xticks(xticks)
    ax.ticklabel_format(style="plain", axis="x")
    ax.set_xlim(min(strikes), max(strikes))
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend()
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    toolbar = NavigationToolbar2Tk(canvas, parent)
    toolbar.update()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    return fig
