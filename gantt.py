
from datetime import datetime
from typing import Dict, List
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch
import pandas as pd

def _palette(n: int) -> List[str]:
    base = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf"]
    if n <= len(base): return base[:n]
    return (base * ((n // len(base)) + 1))[:n]

def generer_gantt_of_ligne_double_cycle(df_std: pd.DataFrame, df_aog: pd.DataFrame,
    titre: str = "Gantt OF — 1 ligne par OF (Std & AOG, couleur par centre)", legend_loc: str = "lower right"
) -> plt.Figure:
    of_union = pd.concat([df_std[["OF"]], df_aog[["OF"]]], ignore_index=True).drop_duplicates()
    n_of = len(of_union)
    fig, ax = plt.subplots(figsize=(13, max(5, 0.7 * max(n_of, 1))))
    df_std2 = df_std.dropna(subset=["Début","Fin"]).copy()
    df_aog2 = df_aog.dropna(subset=["Début","Fin"]).copy()
    if df_std2.empty and df_aog2.empty:
        ax.set_title(titre); return fig
    ord_std = df_std2.groupby("OF", as_index=False)["Début"].min() if not df_std2.empty else pd.DataFrame(columns=["OF","Début"])
    ord_aog = df_aog2.groupby("OF", as_index=False)["Début"].min() if not df_aog2.empty else pd.DataFrame(columns=["OF","Début"])
    ord_all = pd.concat([ord_std, ord_aog], ignore_index=True)
    ylabels = (
        ord_all.groupby("OF", as_index=False)["Début"].min().sort_values("Début")["OF"].tolist()
        if not ord_all.empty else pd.concat([df_std2[["OF"]], df_aog2[["OF"]]]).drop_duplicates()["OF"].tolist()
    )
    y_index = {of: i for i, of in enumerate(ylabels)}
    centres = pd.concat([df_std2["Centre_de_charge"].fillna(""), df_aog2["Centre_de_charge"].fillna("")]).drop_duplicates().tolist()
    colors = _palette(len(centres)); color_map: Dict[str,str] = {c: colors[i] for i, c in enumerate(centres)}
    def _left_width_dates(start, end):
        left = mdates.date2num(pd.Timestamp(start))
        width = mdates.date2num(pd.Timestamp(end)) - left
        return left, width
    for _, row in df_std2.iterrows():
        of = row["OF"]; 
        if of not in y_index: continue
        y = y_index[of]; left, width = _left_width_dates(row["Début"], row["Fin"])
        c = color_map.get(str(row.get("Centre_de_charge","")) or "", "#7f7f7f")
        ax.broken_barh([(left, width)], (y - 0.30, 0.25), facecolors=c, edgecolor="black", alpha=0.9, hatch=None)
    for _, row in df_aog2.iterrows():
        of = row["OF"]; 
        if of not in y_index: continue
        y = y_index[of]; left, width = _left_width_dates(row["Début"], row["Fin"])
        c = color_map.get(str(row.get("Centre_de_charge","")) or "", "#7f7f7f")
        ax.broken_barh([(left, width)], (y + 0.05, 0.25), facecolors=c, edgecolor="#333333", alpha=0.85, hatch="//")
    ax.set_yticks(range(len(ylabels))); ax.set_yticklabels(ylabels); ax.invert_yaxis()
    ax.xaxis_date()
    try:
        MON = getattr(mdates, "MO", None) or getattr(mdates, "MONDAY", None)
        locator = mdates.WeekdayLocator(byweekday=MON, interval=1)
    except Exception:
        locator = mdates.DayLocator(interval=7)
    ax.xaxis.set_major_locator(locator)
    def _iso_week_fmt(x, pos=None):
        dt = mdates.num2date(x); y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"
    ax.xaxis.set_major_formatter(FuncFormatter(_iso_week_fmt))
    ax.set_xlabel("Semaines (année-semaine)")
    ax.set_title(titre); ax.grid(axis="x", linestyle="--", alpha=0.5)
    centre_handles = [Patch(facecolor=color_map[c], edgecolor="black", label=c if c else "(centre indéfini)") for c in centres]
    cycle_std_handle = Patch(facecolor="white", edgecolor="black", label="Cycle Std")
    cycle_aog_handle = Patch(facecolor="white", edgecolor="#333333", hatch="//", label="Cycle AOG")
    handles = centre_handles + [cycle_std_handle, cycle_aog_handle]
    ax.legend(handles=handles, loc=legend_loc, title="Centre de charge & Cycle", ncol=2)
    plt.tight_layout(); return fig
