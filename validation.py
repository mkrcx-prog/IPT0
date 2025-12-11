
import pandas as pd

REQUIRED_OF_COLS = [
    "OF","Article","Quantité","Priorité","Début_au_plus_tôt","Date_limite","Plan_mode",
    "Operation_actuelle_article","Operation_actuelle_etape","Operation_actuelle_op","Avancement_h_actuel"
]

def validate_of_list(df: pd.DataFrame) -> None:
    missing = set(REQUIRED_OF_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes OF manquantes: {sorted(missing)}")
