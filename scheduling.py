
# scheduling.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from data_model import (
    HEURES_TRAVAIL_MATIN, HEURES_TRAVAIL_APRESMIDI, JOURS_TRAVAIL, HEURES_PAR_SEMAINE, ARTICLE_CATALOG,
)

try:
    from data_model import ARTICLE_BOM
except Exception:
    ARTICLE_BOM = pd.DataFrame(columns=["Parent_Article", "Child_Article", "Child_Qty"])

# --- Calendrier ---
def est_jour_travail(d: date) -> bool: return d.weekday() in JOURS_TRAVAIL
def intervales_travail_pour_jour(d: date) -> List[Tuple[datetime, datetime]]:
    return [
        (datetime.combine(d, HEURES_TRAVAIL_MATIN[0]), datetime.combine(d, HEURES_TRAVAIL_MATIN[1])),
        (datetime.combine(d, HEURES_TRAVAIL_APRESMIDI[0]), datetime.combine(d, HEURES_TRAVAIL_APRESMIDI[1])),
    ]
def prochain_moment_travail(dt: datetime) -> datetime:
    while not est_jour_travail(dt.date()):
        dt = datetime.combine(dt.date() + timedelta(days=1), HEURES_TRAVAIL_MATIN[0])
    md, mf = HEURES_TRAVAIL_MATIN; ad, af = HEURES_TRAVAIL_APRESMIDI; t = dt.time()
    if t < md: return datetime.combine(dt.date(), md)
    if md <= t <= mf: return dt
    if mf < t < ad: return datetime.combine(dt.date(), ad)
    if ad <= t <= af: return dt
    nxt = dt.date() + timedelta(days=1)
    while not est_jour_travail(nxt): nxt += timedelta(days=1)
    return datetime.combine(nxt, md)
def precedent_moment_travail(dt: datetime) -> datetime:
    md, mf = HEURES_TRAVAIL_MATIN; ad, af = HEURES_TRAVAIL_APRESMIDI
    while not est_jour_travail(dt.date()):
        dt = datetime.combine(dt.date() - timedelta(days=1), af)
    t = dt.time()
    if t > af: return datetime.combine(dt.date(), af)
    if ad <= t <= af: return dt
    if mf < t < ad: return datetime.combine(dt.date(), mf)
    if md <= t <= mf: return dt
    prev = dt.date() - timedelta(days=1)
    while not est_jour_travail(prev): prev -= timedelta(days=1)
    return datetime.combine(prev, af)
def ajouter_heures_travail(dt: datetime, heures: float) -> datetime:
    if heures <= 0: return prochain_moment_travail(dt)
    restant = float(heures); courant = prochain_moment_travail(dt)
    while restant > 1e-9:
        for debut, fin in intervales_travail_pour_jour(courant.date()):
            if courant < debut: courant = debut
            if debut <= courant < fin:
                dispo = (fin - courant).total_seconds()/3600.0
                pris = min(dispo, restant)
                courant = courant + timedelta(hours=pris)
                restant -= pris
                if restant <= 1e-9: break
        if restant > 1e-9:
            courant = prochain_moment_travail(datetime.combine(courant.date() + timedelta(days=1), HEURES_TRAVAIL_MATIN[0]))
    return courant
def retirer_heures_travail(dt: datetime, heures: float) -> datetime:
    if heures <= 0: return precedent_moment_travail(dt)
    restant = float(heures); courant = precedent_moment_travail(dt)
    while restant > 1e-9:
        for debut, fin in reversed(intervales_travail_pour_jour(courant.date())):
            if courant > fin: courant = fin
            if debut < courant <= fin:
                dispo = (courant - debut).total_seconds()/3600.0
                pris = min(dispo, restant)
                courant = courant - timedelta(hours=pris)
                restant -= pris
                if restant <= 1e-9: break
        if restant > 1e-9:
            prev = courant.date() - timedelta(days=1)
            while not est_jour_travail(prev): prev -= timedelta(days=1)
            courant = datetime.combine(prev, HEURES_TRAVAIL_APRESMIDI[1])
    return courant

# --- Helpers ---
def _parse_date(x) -> Optional[datetime]:
    if pd.isna(x) or x == "": return None
    if isinstance(x, (datetime, pd.Timestamp)): return pd.Timestamp(x).to_pydatetime()
    try: return datetime.fromisoformat(str(x).replace(" ", "T"))
    except Exception: return None

def _expand_article_operations(article: str, qty: int, article_catalog: pd.DataFrame, bom: pd.DataFrame, visited: Optional[set] = None) -> List[dict]:
    if visited is None: visited = set()
    if article in visited: return []
    visited.add(article)
    ops: List[dict] = []
    rows = article_catalog[article_catalog["Article"] == article].copy()
    for _, r in rows.iterrows():
        ops.append({
            "Article_source": article,
            "Étape": int(r.get("Étape", 0) or 0),
            "Opération": str(r.get("Opération", "")),
            "Centre_de_charge": str(r.get("Centre_de_charge", "") or ""),
            "Charge_h": float(r.get("Charge_h", 0.0) or 0.0) * qty,
            "Semaines_Std": int(r.get("Semaines_Std", 0) or 0),
            "Semaines_AOG": int(r.get("Semaines_AOG", 0) or 0),
        })
    children = bom[bom["Parent_Article"] == article]
    for _, c in children.iterrows():
        child = str(c.get("Child_Article", "")).strip()
        child_qty = int(c.get("Child_Qty", 1) or 1) * qty
        if not child: continue
        ops.extend(_expand_article_operations(child, child_qty, article_catalog, bom, visited))
    return ops

def _build_windows_sequence_forward(ops_seq: List[dict], start_anchor: datetime, cycle_label: str) -> List[dict]:
    enriched = []; current_start = start_anchor
    for r in ops_seq:
        sem = int(r.get(f"Semaines_{cycle_label}", 0) or 0)
        window_h = sem * HEURES_PAR_SEMAINE if sem > 0 else max(float(r.get("Charge_h", 0.0) or 0.0), 1e-9)
        start_t = prochain_moment_travail(current_start)
        end_t = ajouter_heures_travail(start_t, window_h)
        enriched.append({**r, "Fenêtre_début": start_t, "Fenêtre_fin": end_t, "Window_h": window_h})
        current_start = end_t
    return enriched

def _build_windows_sequence_backward(ops_seq: List[dict], end_anchor: datetime, cycle_label: str) -> List[dict]:
    enriched_rev = []; current_end = end_anchor
    for r in reversed(ops_seq):
        sem = int(r.get(f"Semaines_{cycle_label}", 0) or 0)
        window_h = sem * HEURES_PAR_SEMAINE if sem > 0 else max(float(r.get("Charge_h", 0.0) or 0.0), 1e-9)
        end_t = precedent_moment_travail(current_end)
        start_t = retirer_heures_travail(end_t, window_h)
        enriched_rev.append({**r, "Fenêtre_début": start_t, "Fenêtre_fin": end_t, "Window_h": window_h})
        current_end = start_t
    enriched = list(reversed(enriched_rev))
    return enriched

def _verify_component_precedence(ops_with_windows: List[dict], parent_article: str) -> List[str]:
    anomalies = []
    if not ops_with_windows: return anomalies
    assembly_windows = [r for r in ops_with_windows if str(r.get("Article_source")) == parent_article]
    comps_windows   = [r for r in ops_with_windows if str(r.get("Article_source")) != parent_article]
    if not assembly_windows or not comps_windows: return anomalies
    assembly_start_min = min(w["Fenêtre_début"] for w in assembly_windows if w.get("Fenêtre_début") is not None)
    for w in comps_windows:
        comp_fin = w.get("Fenêtre_fin")
        if comp_fin and assembly_start_min and comp_fin > assembly_start_min + timedelta(seconds=1e-6):
            anomalies.append("Préséance violée: composant finit après le début d’assemblage.")
    return anomalies

def _slice_ops_from_current(
    ops_sorted: List[dict], parent_article: str,
    cur_src: Optional[str], cur_step: Optional[int],
    cur_op_name: Optional[str], cur_progress_h: float, anomalies_of: List[str],
) -> List[dict]:
    if not cur_src: return ops_sorted
    threshold = None
    if cur_step is not None:
        threshold = int(cur_step)
    elif cur_op_name:
        for r in ops_sorted:
            if str(r["Article_source"]) == cur_src and str(r.get("Opération","")) == cur_op_name:
                threshold = int(r.get("Étape", 0)); break
    if threshold is None:
        anomalies_of.append(f"Operation_actuelle introuvable dans '{cur_src}' — planification complète.")
        return ops_sorted

    new_ops: List[dict] = []
    for r in ops_sorted:
        src = str(r["Article_source"]); step = int(r.get("Étape", 0))
        if cur_src == parent_article and src != parent_article:  # reprise assemblage: supprimer composants
            continue
        if cur_src != parent_article and src != cur_src and src != parent_article:  # reprendre sur une branche: ignorer autres
            continue
        if src == cur_src and step < threshold:  # ignorer étapes antérieures
            continue
        if src == cur_src and step == threshold and cur_progress_h > 0:  # avancement
            r = {**r}
            r["Charge_h"] = max(0.0, float(r.get("Charge_h", 0.0) or 0.0) - float(cur_progress_h))
        new_ops.append(r)
    if cur_src == parent_article:
        anomalies_of.append("Reprise sur assemblage : composants présumés réalisés (non replanifiés).")
    return new_ops

# --- Moteur ---
def planifier_of_list_for_cycle(
    of_list: pd.DataFrame, article_catalog: pd.DataFrame, debut_projet: datetime,
    cycle_label: str, capacites_centre: Optional[Dict[str, float]] = None, bom: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    cap = capacites_centre or {}
    bom_df = bom if bom is not None else ARTICLE_BOM

    of_df = of_list.copy()
    of_df["Date_limite"] = of_df.get("Date_limite", "").apply(_parse_date)
    of_df["Début_au_plus_tôt"] = of_df.get("Début_au_plus_tôt", "").apply(_parse_date)
    of_df["Priorité"] = pd.to_numeric(of_df.get("Priorité", 3), errors="coerce").fillna(3).astype(int)
    of_df["Quantité"] = pd.to_numeric(of_df.get("Quantité", 1), errors="coerce").fillna(1).astype(int)
    of_df["Plan_mode"] = of_df.get("Plan_mode", "").fillna("ASAP").astype(str).str.upper()
    of_df["Operation_actuelle_article"] = of_df.get("Operation_actuelle_article", "").fillna("").astype(str)
    of_df["Operation_actuelle_etape"] = pd.to_numeric(of_df.get("Operation_actuelle_etape", None), errors="coerce")
    of_df["Operation_actuelle_op"] = of_df.get("Operation_actuelle_op", "").fillna("").astype(str)
    of_df["Avancement_h_actuel"] = pd.to_numeric(of_df.get("Avancement_h_actuel", 0.0), errors="coerce").fillna(0.0)

    capacite_restante: Dict[date, Dict[str, float]] = defaultdict(dict)
    def get_cap_jour(jour: date, centre: str) -> float:
        if centre in capacite_restante[jour]: return capacite_restante[jour][centre]
        return float(cap.get(centre, float("inf")))  # ∞ si centre non défini
    def consommer_cap(jour: date, centre: str, heures: float) -> float:
        dispo = get_cap_jour(jour, centre)
        pris = min(dispo, max(0.0, heures))
        capacite_restante[jour][centre] = dispo - pris
        return pris

    segments: List[dict] = []

    for _, ofrow in of_df.iterrows():
        of_name = str(ofrow.get("OF", "")).strip()
        article = str(ofrow.get("Article", "")).strip()
        qty = int(ofrow.get("Quantité", 1))
        debut_min = ofrow.get("Début_au_plus_tôt") or debut_projet
        dl = ofrow.get("Date_limite")
        mode = (ofrow.get("Plan_mode") or "ASAP").upper()
        anomalies_of: List[str] = []

        cur_src     = ofrow.get("Operation_actuelle_article") or None
        cur_step    = int(ofrow["Operation_actuelle_etape"]) if pd.notna(ofrow.get("Operation_actuelle_etape")) else None
        cur_op_name = ofrow.get("Operation_actuelle_op") or None
        cur_prog_h  = float(ofrow.get("Avancement_h_actuel", 0.0) or 0.0)

        if not of_name or not article: continue

        ops = _expand_article_operations(article, qty, article_catalog, bom_df, visited=set())
        ops_sorted = sorted(ops, key=lambda r: (str(r["Article_source"]), int(r.get("Étape", 0))))
        ops_sorted = _slice_ops_from_current(ops_sorted, article, cur_src, cur_step, cur_op_name, cur_prog_h, anomalies_of)

        assembly_ops = [r for r in ops_sorted if str(r["Article_source"]) == article]
        components_map: Dict[str, List[dict]] = {}
        for r in ops_sorted:
            src = str(r["Article_source"])
            if src == article: continue
            components_map.setdefault(src, []).append(r)

        if mode == "RETRO":
            if not isinstance(dl, datetime):
                anomalies_of.append("Mode RETRO sans Date limite (OF) — fallback ASAP.")
                comp_enriched_all: List[dict] = []; branch_ends: List[datetime] = []
                for src, seq in components_map.items():
                    enriched = _build_windows_sequence_forward(sorted(seq, key=lambda r: int(r.get("Étape", 0))), debut_min, cycle_label)
                    comp_enriched_all.extend(enriched); 
                    if enriched: branch_ends.append(enriched[-1]["Fenêtre_fin"])
                assembly_start = max(branch_ends) if branch_ends else debut_min
                assembly_enriched = _build_windows_sequence_forward(sorted(assembly_ops, key=lambda r: int(r.get("Étape", 0))), assembly_start, cycle_label)
                ops_with_windows = comp_enriched_all + assembly_enriched
            else:
                end_anchor = precedent_moment_travail(dl)
                assembly_enriched = _build_windows_sequence_backward(sorted(assembly_ops, key=lambda r: int(r.get("Étape", 0))), end_anchor, cycle_label)
                assembly_start = assembly_enriched[0]["Fenêtre_début"] if assembly_enriched else end_anchor
                comp_enriched_all: List[dict] = []
                for src, seq in components_map.items():
                    enriched = _build_windows_sequence_backward(sorted(seq, key=lambda r: int(r.get("Étape", 0))), assembly_start, cycle_label)
                    comp_enriched_all.extend(enriched)
                ops_with_windows = comp_enriched_all + assembly_enriched
        else:
            if cur_src and isinstance(debut_min, datetime):
                comp_enriched_all: List[dict] = []
                if assembly_ops and cur_src == article:
                    assembly_enriched = _build_windows_sequence_forward(sorted(assembly_ops, key=lambda r: int(r.get("Étape", 0))), debut_min, cycle_label)
                    ops_with_windows = assembly_enriched
                else:
                    for src, seq in components_map.items():
                        if src != cur_src: continue
                        enriched = _build_windows_sequence_forward(sorted(seq, key=lambda r: int(r.get("Étape", 0))), debut_min, cycle_label)
                        comp_enriched_all.extend(enriched)
                    branch_ends = [en["Fenêtre_fin"] for en in comp_enriched_all] if comp_enriched_all else []
                    assembly_start = max(branch_ends) if branch_ends else debut_min
                    assembly_enriched = _build_windows_sequence_forward(sorted(assembly_ops, key=lambda r: int(r.get("Étape", 0))), assembly_start, cycle_label)
                    ops_with_windows = comp_enriched_all + assembly_enriched
            else:
                comp_enriched_all: List[dict] = []; branch_ends: List[datetime] = []
                for src, seq in components_map.items():
                    enriched = _build_windows_sequence_forward(sorted(seq, key=lambda r: int(r.get("Étape", 0))), debut_min, cycle_label)
                    comp_enriched_all.extend(enriched); 
                    if enriched: branch_ends.append(enriched[-1]["Fenêtre_fin"])
                assembly_start = max(branch_ends) if branch_ends else debut_min
                assembly_enriched = _build_windows_sequence_forward(sorted(assembly_ops, key=lambda r: int(r.get("Étape", 0))), assembly_start, cycle_label)
                ops_with_windows = comp_enriched_all + assembly_enriched

        if any(str(r.get("Article_source")) != article for r in ops_with_windows):
            anomalies_of.extend(_verify_component_precedence(ops_with_windows, article))

        if mode == "ASAP":
            final_end_target = ops_with_windows[-1]["Fenêtre_fin"] if ops_with_windows else debut_min
            if isinstance(dl, datetime) and final_end_target > dl:
                anomalies_of.append("Fin cible > Date limite (OF)")
        else:
            first_start_target = ops_with_windows[0]["Fenêtre_début"] if ops_with_windows else debut_min
            if isinstance(debut_min, datetime) and first_start_target < debut_min:
                anomalies_of.append("Début calculé < Début_au_plus_tôt (OF)")

        for r in ops_with_windows:
            op = str(r.get("Opération", "")); centre = str(r.get("Centre_de_charge", "") or "")
            charge_h = float(r.get("Charge_h", 0.0) or 0.0)
            semaines_cibles = int(r.get(f"Semaines_{cycle_label}", 0) or 0)

            start_seg = r["Fenêtre_début"]
            end_target = r["Fenêtre_fin"]  # fin cible (fenêtre)
            courant = start_seg
            restant = max(0.0, charge_h)
            heures_realisees = 0.0
            end_seg = end_target  # fin réelle
            decallage_h = 0.0

            while restant > 1e-9:
                if not est_jour_travail(courant.date()):
                    courant = prochain_moment_travail(datetime.combine(courant.date() + timedelta(days=1), HEURES_TRAVAIL_MATIN[0]))
                intervals = intervales_travail_pour_jour(courant.date())
                avance = False
                for debut_int, fin_int in intervals:
                    if courant < debut_int: courant = debut_int
                    fin_limit = fin_int
                    # autoriser au-delà de la fenêtre cible si capacité insuffisante
                    if fin_int > end_target and heures_realisees < charge_h:
                        fin_limit = fin_int
                    if not (debut_int <= courant < fin_limit): continue
                    dispo_intervalle = (fin_limit - courant).total_seconds()/3600.0
                    if dispo_intervalle <= 1e-9: continue
                    cap_jour = get_cap_jour(courant.date(), centre)  # ∞ si centre non défini
                    pris = min(dispo_intervalle, cap_jour, restant)
                    if pris > 0:
                        consommer_cap(courant.date(), centre, pris)
                        courant = courant + timedelta(hours=pris)
                        restant -= pris; heures_realisees += pris
                        end_seg = courant; avance = True
                    if restant <= 1e-9: break
                if restant > 1e-9 and not avance:
                    next_morning = datetime.combine(courant.date() + timedelta(days=1), HEURES_TRAVAIL_MATIN[0])
                    courant = prochain_moment_travail(next_morning)

            if end_seg > end_target:
                decallage_h = (end_seg - end_target).total_seconds() / 3600.0
                anomalies_of.append(f"Décalage de fin (+{decallage_h:.1f} h ; +{decallage_h/HEURES_PAR_SEMAINE:.2f} sem.)")
            duree_h = (end_seg - start_seg).total_seconds() / 3600.0
            duree_sem = duree_h / HEURES_PAR_SEMAINE
            ecart_sem = duree_sem - float(semaines_cibles or 0)
            if isinstance(dl, datetime) and end_seg > dl:
                anomalies_of.append("Fin réelle > Date limite (OF)")

            segments.append({
                "OF": of_name, "Article_source": r["Article_source"], "Article": article,
                "Opération": op, "Centre_de_charge": centre, "Cycle": cycle_label, "Plan_mode": mode,
                "Étape": int(r.get("Étape", 0) or 0), "Charge_h": round(charge_h, 2),
                "Semaines_cibles": int(semaines_cibles or 0),
                "Fenêtre_début": start_seg, "Fenêtre_fin": end_target, "Début": start_seg, "Fin": end_seg,
                "Décalage_fin_h": round(decallage_h, 2), "Décalage_fin_sem": round(decallage_h/HEURES_PAR_SEMAINE, 2),
                "Heures_réalisées": round(heures_realisees, 2), "Heures_non_planifiées": round(max(0.0, charge_h - heures_realisees), 2),
                "Durée_h": round(duree_h, 2), "Durée_semaines": round(duree_sem, 2), "Écart_semaines": round(ecart_sem, 2),
                "Date_limite": dl, "Anomalie": True if anomalies_of else False, "Commentaires": "; ".join(anomalies_of),
            })

    return pd.DataFrame(segments)

def planifier_of_both_cycles(
    of_list: pd.DataFrame, article_catalog: pd.DataFrame = ARTICLE_CATALOG,
    debut_projet: datetime = None, capacites_centre: Optional[Dict[str, float]] = None, bom: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if debut_projet is None: debut_projet = datetime.now()
    df_std = planifier_of_list_for_cycle(of_list, article_catalog, debut_projet, "Std", capacites_centre, bom)
    df_aog = planifier_of_list_for_cycle(of_list, article_catalog, debut_projet, "AOG", capacites_centre, bom)
    return df_std, df_aog
