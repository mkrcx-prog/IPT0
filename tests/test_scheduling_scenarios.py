import pandas as pd
from datetime import datetime
from scheduling import planifier_of_both_cycles
from data_model import ARTICLE_CATALOG, ARTICLE_BOM

def _of(of, article, qty=1, start=None, due=None, mode="ASAP", cur_src="", cur_step=None, cur_op="", cur_prog_h=0.0):
    return {
        "OF": of, "Article": article, "Quantité": qty, "Priorité": 2,
        "Début_au_plus_tôt": start, "Date_limite": due, "Plan_mode": mode,
        "Operation_actuelle_article": cur_src, "Operation_actuelle_etape": cur_step,
        "Operation_actuelle_op": cur_op, "Avancement_h_actuel": cur_prog_h
    }

def test_asap_longest_branch_then_assembly():
    of_list = pd.DataFrame([_of("OF-001","A100",qty=1,start=datetime(2026,1,5,9,0))])
    df_std, df_aog = planifier_of_both_cycles(of_list, ARTICLE_CATALOG, datetime(2026,1,5,9,0), bom=ARTICLE_BOM)
    g = df_std[df_std["OF"]=="OF-001"]
    parent = g["Article"].iloc[0]
    assembly = g[g["Article_source"]==parent]
    comps   = g[g["Article_source"]!=parent]
    assert assembly["Début"].min() >= comps["Fin"].max()

def test_retro_respects_due_or_flags_delay():
    due = datetime(2026,1,30,17,0)
    of_list = pd.DataFrame([_of("OF-002","B200",qty=1,start=datetime(2026,1,5,9,0),due=due,mode="RETRO")])
    df_std, _ = planifier_of_both_cycles(of_list, ARTICLE_CATALOG, datetime(2026,1,5,9,0), bom=ARTICLE_BOM)
    g = df_std[df_std["OF"]=="OF-002"]
    assert (g["Fin"].max() <= due) or any("Fin réelle > Date limite" in c for c in g["Commentaires"])
