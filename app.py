
from datetime import datetime, time
import pandas as pd
import streamlit as st

from scheduling import planifier_of_both_cycles
from gantt import generer_gantt_of_ligne_double_cycle
from data_model import ARTICLE_CATALOG, CAPACITES_CENTRE
try:
    from data_model import ARTICLE_BOM
except Exception:
    ARTICLE_BOM = pd.DataFrame(columns=["Parent_Article", "Child_Article", "Child_Qty"])

# --- Helpers ---
def ensure_columns(df: pd.DataFrame, required_defaults: dict) -> pd.DataFrame:
    df2 = df.copy()
    for col, default in required_defaults.items():
        if col not in df2.columns:
            df2[col] = default
    ordered = list(required_defaults.keys()) + [c for c in df2.columns if c not in required_defaults]
    return df2[ordered]

def fmt_dt(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)): return ""
    try: return pd.Timestamp(x).strftime("%d/%m/%Y %H:%M")
    except Exception:
        try: return x.strftime("%d/%m/%Y %H:%M")
        except Exception: return ""

def keep_critical_path_branch(df: pd.DataFrame) -> pd.DataFrame:
    """Par OF/Cycle: composant le plus long + toutes les opérations d’assemblage."""
    if df.empty: return df.copy()
    required = {"OF","Cycle","Article","Article_source","Début","Fin"}
    if not required.issubset(df.columns): return df.copy()
    base = df.dropna(subset=["Début","Fin"]).copy()
    if base.empty: return df.copy()

    keep_rows = []
    for (of, cyc), grp in base.groupby(["OF","Cycle"]):
        parent_article = grp["Article"].iloc[0] if "Article" in grp.columns and not grp["Article"].isna().all() else None
        if parent_article is None:
            comp_dur = grp.groupby("Article_source").agg(dmin=("Début","min"), dmax=("Fin","max"))
            comp_dur["dur_h"] = (comp_dur["dmax"] - comp_dur["dmin"]).dt.total_seconds()/3600.0
            longest_src = comp_dur.sort_values("dur_h", ascending=False).index[0]
            keep_rows.append(grp[grp["Article_source"] == longest_src]); 
            continue
        assembly_rows = grp[grp["Article_source"] == parent_article]
        comp_rows = grp[grp["Article_source"] != parent_article]
        if comp_rows.empty:
            keep_rows.append(grp); continue
        comp_dur = comp_rows.groupby("Article_source").agg(dmin=("Début","min"), dmax=("Fin","max"))
        comp_dur["dur_h"] = (comp_dur["dmax"] - comp_dur["dmin"]).dt.total_seconds()/3600.0
        longest_src = comp_dur.sort_values("dur_h", ascending=False).index[0]
        longest_branch = grp[grp["Article_source"] == longest_src]
        keep_rows.append(pd.concat([longest_branch, assembly_rows], ignore_index=True))
    return pd.concat(keep_rows, ignore_index=True)

# --- Config colonnes / modèles ---
CAT_REQUIRED_DEFAULTS = {
    "Article": "", "Étape": 1, "Opération": "", "Centre_de_charge": "",
    "Charge_h": 0.0, "Semaines_Std": 0, "Semaines_AOG": 0,
}
BOM_REQUIRED_DEFAULTS = { "Parent_Article": "", "Child_Article": "", "Child_Qty": 1 }
OF_REQUIRED_DEFAULTS = {
    "OF": "", "Article": "", "Quantité": 1, "Priorité": 3,
    "Début_au_plus_tôt": None, "Date_limite": None, "Plan_mode": "ASAP",
    # Reprise :
    "Operation_actuelle_article": "",     # branche/Article_source (parent ou composant)
    "Operation_actuelle_etape": None,     # n° d'étape (prioritaire si rempli)
    "Operation_actuelle_op": "",          # nom exact de l'opération (si pas d'étape)
    "Avancement_h_actuel": 0.0,           # heures déjà faites sur l'opération actuelle
}
OF_TEMPLATE = pd.DataFrame({
    "OF": ["OF-001", "OF-002"],
    "Article": ["A100", "B200"],
    "Quantité": [10, 5],
    "Priorité": [2, 1],
    "Début_au_plus_tôt": [None, None],
    "Date_limite": [None, None],
    "Plan_mode": ["ASAP", "RETRO"],
    "Operation_actuelle_article": ["", ""],
    "Operation_actuelle_etape": [None, None],
    "Operation_actuelle_op": ["", ""],
    "Avancement_h_actuel": [0.0, 0.0],
})

# --- UI ---
st.set_page_config(page_title="IPT — OF par articles (Std & AOG)", layout="wide")

st.title("🧱 Interactive Planification Tool — OF par articles (Std & AOG)")
st.caption(
    "Le **cycle** fixe la **durée** (semaines). **ASAP** : start au plus tôt → composants // → **assemblage** après la plus longue branche. "
    "**RETRO** : **assemblage** arrimé à **Date limite** → composants finissent avant. "
    "Reprise possible: **opération actuelle** (branche + étape/nom) démarrant à **Début au plus tôt** en ASAP. "
    "Si la **capacité** ne suffit pas → **décalage** et **anomalie**."
)

# Résultats persistants
if "df_std" not in st.session_state: st.session_state["df_std"] = pd.DataFrame()
if "df_aog" not in st.session_state: st.session_state["df_aog"] = pd.DataFrame()
if "has_results" not in st.session_state: st.session_state["has_results"] = False

# Barre latérale
st.sidebar.header("Configuration")
date_input = st.sidebar.date_input("Date de début du projet", value=datetime.now())
heure_input = st.sidebar.time_input("Heure de début", value=time(9, 0))
start_datetime = datetime.combine(date_input, heure_input)
st.sidebar.markdown("---")
if st.sidebar.button("Effacer les résultats"):
    st.session_state["df_std"] = pd.DataFrame(); st.session_state["df_aog"] = pd.DataFrame()
    st.session_state["has_results"] = False
    st.toast("Résultats effacés.")

# États Session entrées
if "article_catalog" not in st.session_state:
    st.session_state["article_catalog"] = ensure_columns(ARTICLE_CATALOG.copy(), CAT_REQUIRED_DEFAULTS)
    st.session_state["file_loaded_catalog"] = False
if "article_bom" not in st.session_state:
    st.session_state["article_bom"] = ensure_columns(ARTICLE_BOM.copy(), BOM_REQUIRED_DEFAULTS)
    st.session_state["file_loaded_bom"] = False
if "capacites_centre" not in st.session_state:
    st.session_state["capacites_centre"] = CAPACITES_CENTRE.copy()
if "of_list" not in st.session_state:
    st.session_state["of_list"] = ensure_columns(OF_TEMPLATE.copy(), OF_REQUIRED_DEFAULTS)

# Uploads
uploaded_catalog = st.sidebar.file_uploader("Importer catalogue Article-Opérations (.xlsx)", type=["xlsx"])
if uploaded_catalog is not None and not st.session_state["file_loaded_catalog"]:
    try:
        cat_uploaded = pd.read_excel(uploaded_catalog)
        st.session_state["article_catalog"] = ensure_columns(cat_uploaded, CAT_REQUIRED_DEFAULTS)
        st.session_state["file_loaded_catalog"] = True
        st.toast("Catalogue d'articles chargé.")
    except Exception as e:
        st.error(f"Erreur lecture catalogue : {e}")

uploaded_bom = st.sidebar.file_uploader("Importer BOM / sous-composants (.xlsx)", type=["xlsx"])
if uploaded_bom is not None and not st.session_state["file_loaded_bom"]:
    try:
        bom_uploaded = pd.read_excel(uploaded_bom)
        st.session_state["article_bom"] = ensure_columns(bom_uploaded, BOM_REQUIRED_DEFAULTS)
        st.session_state["file_loaded_bom"] = True
        st.toast("BOM chargée.")
    except Exception as e:
        st.error(f"Erreur lecture BOM : {e}")

if st.sidebar.button("Réinitialiser catalogue & BOM"):
    from data_model import ARTICLE_CATALOG, ARTICLE_BOM
    st.session_state["article_catalog"] = ensure_columns(ARTICLE_CATALOG.copy(), CAT_REQUIRED_DEFAULTS)
    st.session_state["article_bom"] = ensure_columns(ARTICLE_BOM.copy(), BOM_REQUIRED_DEFAULTS)
    st.session_state["file_loaded_catalog"] = False
    st.session_state["file_loaded_bom"] = False
    st.experimental_rerun()

# Édition
st.subheader("1) Catalogue d'articles (Opérations & Durées cible)")
st.caption("✅ **Charge (h)** identique en **Cycle Std/AOG**. ✅ **Durée** fixée par **Semaines_Std/AOG**.")
cat_edit = st.data_editor(st.session_state["article_catalog"], num_rows="dynamic", hide_index=True, key="catalog_editor")

st.subheader("2) BOM / Sous-composants (optionnel)")
st.caption("Relie un **Article parent** à ses **composants** (*Child_Article*, *Child_Qty*).")
bom_edit = st.data_editor(st.session_state["article_bom"], num_rows="dynamic", hide_index=True, key="bom_editor")

st.subheader("3) Capacités par centre de charge (heures/jour)")
st.caption("Centre non défini ⇒ capacité infinie.")
cap_df = pd.DataFrame([{"Centre_de_charge": k, "Capacité_h_jour": v} for k, v in st.session_state["capacites_centre"].items()])
cap_edit = st.data_editor(cap_df, num_rows="dynamic", hide_index=True, key="cap_editor")
capacites_centre = {
    str(row["Centre_de_charge"]).strip(): (None if pd.isna(row["Capacité_h_jour"]) else float(row["Capacité_h_jour"]))
    for _, row in cap_edit.iterrows() if str(row["Centre_de_charge"]).strip() != ""
}
capacites_centre = {k: v for k, v in capacites_centre.items() if v is not None}

st.subheader("4) Liste des OF à planifier")
st.caption("**ASAP**: démarre au **Début au plus tôt** (si renseigné). **RETRO**: utilise la **Date limite**. "
           "Reprise: indiquer **Operation_actuelle_article** (branche/parent) + **étape** ou **nom**, et **Avancement_h_actuel**.")
of_edit = st.data_editor(ensure_columns(st.session_state["of_list"], OF_REQUIRED_DEFAULTS),
                         num_rows="dynamic", hide_index=True, key="of_list_editor")

# Calcul
if st.button("▶️ Planifier (Std & AOG)"):
    with st.spinner("Calcul en cours..."):
        df_std, df_aog = planifier_of_both_cycles(
            of_list=of_edit, article_catalog=cat_edit,
            debut_projet=start_datetime, capacites_centre=capacites_centre, bom=bom_edit
        )
    st.session_state["df_std"] = df_std; st.session_state["df_aog"] = df_aog
    st.session_state["has_results"] = True
    st.success("Planning calculé.")

# Affichage persistant
if st.session_state["has_results"]:
    df_std = st.session_state["df_std"]; df_aog = st.session_state["df_aog"]

    tab_std, tab_aog, tab_gantt, tab_anom = st.tabs(["🔵 Std", "🟠 AOG", "📊 Gantt (branche critique)", "⚠️ Anomalies"])

    with tab_std:
        fin_proj_std = pd.to_datetime(df_std["Fin"]).max() if not df_std.empty else None
        total_charge_std = float(df_std["Charge_h"].sum()) if not df_std.empty else 0.0
        total_semaines_std = float(df_std["Durée_semaines"].sum()) if not df_std.empty else 0.0
        anom_std = int(df_std[df_std.get("Anomalie", False) == True].shape[0]) if not df_std.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fin (Std)", fmt_dt(fin_proj_std)); c2.metric("Charge (h)", f"{total_charge_std:.1f}")
        c3.metric("Durée (sem.)", f"{total_semaines_std:.2f}"); c4.metric("Anomalies", f"{anom_std}")
        st.dataframe(df_std[[
            "OF","Article","Article_source","Étape","Opération","Centre_de_charge",
            "Plan_mode","Semaines_cibles","Charge_h","Fenêtre_début","Fenêtre_fin","Début","Fin",
            "Décalage_fin_h","Décalage_fin_sem",
            "Heures_réalisées","Heures_non_planifiées","Durée_h","Durée_semaines","Écart_semaines",
            "Date_limite","Anomalie","Commentaires"
        ]].style.format({
            "Fenêtre_début": fmt_dt, "Fenêtre_fin": fmt_dt, "Début": fmt_dt, "Fin": fmt_dt, "Date_limite": fmt_dt,
            "Charge_h": "{:.1f}", "Décalage_fin_h": "{:.1f}", "Décalage_fin_sem": "{:.2f}",
            "Heures_réalisées": "{:.1f}", "Heures_non_planifiées": "{:.1f}",
            "Durée_h": "{:.1f}", "Durée_semaines": "{:.2f}", "Écart_semaines": "{:.2f}",
        }))

    with tab_aog:
        fin_proj_aog = pd.to_datetime(df_aog["Fin"]).max() if not df_aog.empty else None
        total_charge_aog = float(df_aog["Charge_h"].sum()) if not df_aog.empty else 0.0
        total_semaines_aog = float(df_aog["Durée_semaines"].sum()) if not df_aog.empty else 0.0
        anom_aog = int(df_aog[df_aog.get("Anomalie", False) == True].shape[0]) if not df_aog.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fin (AOG)", fmt_dt(fin_proj_aog)); c2.metric("Charge (h)", f"{total_charge_aog:.1f}")
        c3.metric("Durée (sem.)", f"{total_semaines_aog:.2f}"); c4.metric("Anomalies", f"{anom_aog}")
        st.dataframe(df_aog[[
            "OF","Article","Article_source","Étape","Opération","Centre_de_charge",
            "Plan_mode","Semaines_cibles","Charge_h","Fenêtre_début","Fenêtre_fin","Début","Fin",
            "Décalage_fin_h","Décalage_fin_sem",
            "Heures_réalisées","Heures_non_planifiées","Durée_h","Durée_semaines","Écart_semaines",
            "Date_limite","Anomalie","Commentaires"
        ]].style.format({
            "Fenêtre_début": fmt_dt, "Fenêtre_fin": fmt_dt, "Début": fmt_dt, "Fin": fmt_dt, "Date_limite": fmt_dt,
            "Charge_h": "{:.1f}", "Décalage_fin_h": "{:.1f}", "Décalage_fin_sem": "{:.2f}",
            "Heures_réalisées": "{:.1f}", "Heures_non_planifiées": "{:.1f}",
            "Durée_h": "{:.1f}", "Durée_semaines": "{:.2f}", "Écart_semaines": "{:.2f}",
        }))

    with tab_gantt:
        st.caption("Gantt = **branche critique par défaut** (composant le plus long + assemblage).")
        df_std_plot = keep_critical_path_branch(df_std)
        df_aog_plot = keep_critical_path_branch(df_aog)
        fig = generer_gantt_of_ligne_double_cycle(
            df_std_plot, df_aog_plot,
            titre="Gantt OF — branche critique (composant le plus long + assemblage)",
            legend_loc="lower right",
        )
        st.pyplot(fig)

    with tab_anom:
        st.caption("Anomalies (capacité/décalage, date limite dépassée, rétro sans limite, début < au plus tôt, préséance, charge non planifiable).")
        anomalies = pd.concat([df_std, df_aog], ignore_index=True)
        anomalies = anomalies[(anomalies.get("Anomalie", False) == True) | (anomalies.get("Commentaires","") != "")]
        if anomalies.empty:
            st.success("Aucune anomalie détectée.")
        else:
            st.dataframe(anomalies[[
                "OF","Cycle","Plan_mode","Article","Article_source","Étape","Opération",
                "Semaines_cibles","Charge_h","Fenêtre_début","Fenêtre_fin","Début","Fin",
                "Décalage_fin_h","Décalage_fin_sem",
                "Heures_non_planifiées","Date_limite","Commentaires"
            ]].style.format({
                "Fenêtre_début": fmt_dt, "Fenêtre_fin": fmt_dt, "Début": fmt_dt, "Fin": fmt_dt, "Date_limite": fmt_dt,
                "Charge_h": "{:.1f}", "Décalage_fin_h": "{:.1f}", "Décalage_fin_sem": "{:.2f}",
                "Heures_non_planifiées": "{:.1f}",
            }))

    # Export
    st.subheader("Export")
    try:
        from export import creer_excel_export_segments
        xls = creer_excel_export_segments(pd.concat([df_std.assign(Cycle="Std"), df_aog.assign(Cycle="AOG")], ignore_index=True))
    except Exception:
        import io
        buffer = io.BytesIO()
        all_df = pd.concat([df_std.assign(Cycle="Std"), df_aog.assign(Cycle="AOG")], ignore_index=True)
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            all_df.to_excel(writer, index=False, sheet_name="Segments")
        buffer.seek(0)
        xls = buffer.getvalue()
    st.download_button("💾 Télécharger (.xlsx)", data=xls,
                       file_name=f"planning_OF_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.ms-excel", key="dl_export_main")
