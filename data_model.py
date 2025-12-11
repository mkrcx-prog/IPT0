
from datetime import time
import pandas as pd

HEURES_TRAVAIL_MATIN = (time(9, 0), time(12, 0))
HEURES_TRAVAIL_APRESMIDI = (time(13, 0), time(17, 0))
JOURS_TRAVAIL = {0, 1, 2, 3, 4}
HEURES_PAR_JOUR = (HEURES_TRAVAIL_MATIN[1].hour - HEURES_TRAVAIL_MATIN[0].hour) + (HEURES_TRAVAIL_APRESMIDI[1].hour - HEURES_TRAVAIL_APRESMIDI[0].hour)
HEURES_PAR_SEMAINE = HEURES_PAR_JOUR * 5

ARTICLE_CATALOG = pd.DataFrame(
    [
        {"Article": "A100", "Étape": 1, "Opération": "Assemblage_1", "Centre_de_charge": "CC-ASM", "Charge_h": 14.0, "Semaines_Std": 1, "Semaines_AOG": 1},
        {"Article": "A100", "Étape": 2, "Opération": "Assemblage_2", "Centre_de_charge": "CC-ASM", "Charge_h": 7.0,  "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "C300", "Étape": 1, "Opération": "Usinage_C300",  "Centre_de_charge": "CC-C300", "Charge_h": 35.0, "Semaines_Std": 1, "Semaines_AOG": 1},
        {"Article": "C300", "Étape": 2, "Opération": "Contrôle_C300", "Centre_de_charge": "CC-QC",   "Charge_h": 14.0, "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "X110", "Étape": 1, "Opération": "Préparation_X110", "Centre_de_charge": "CC-PREP", "Charge_h": 14.0, "Semaines_Std": 1, "Semaines_AOG": 1},
        {"Article": "X110", "Étape": 2, "Opération": "Finition_X110",   "Centre_de_charge": "CC-C300", "Charge_h": 14.0, "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "D400", "Étape": 1, "Opération": "Peinture_D400", "Centre_de_charge": "CC-PAINT", "Charge_h": 21.0, "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "B200", "Étape": 1, "Opération": "Assemblage_B1", "Centre_de_charge": "CC-ASM",   "Charge_h": 10.5, "Semaines_Std": 1, "Semaines_AOG": 1},
        {"Article": "B200", "Étape": 2, "Opération": "Assemblage_B2", "Centre_de_charge": "CC-ASM",   "Charge_h": 7.0,  "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "E500", "Étape": 1, "Opération": "Découpe_E500",  "Centre_de_charge": "CC-E500",  "Charge_h": 21.0, "Semaines_Std": 2, "Semaines_AOG": 1},
        {"Article": "E500", "Étape": 2, "Opération": "Montage_E500",  "Centre_de_charge": "CC-E500",  "Charge_h": 14.0, "Semaines_Std": 1, "Semaines_AOG": 1},

        {"Article": "Z900", "Étape": 1, "Opération": "Op_Z900_1", "Centre_de_charge": "CC-UNDEF", "Charge_h": 28.0, "Semaines_Std": 1, "Semaines_AOG": 1},
    ]
)

CAPACITES_CENTRE = {
    "CC-ASM":   6.0,
    "CC-C300":  8.0,
    "CC-QC":    6.0,
    "CC-PREP":  5.0,
    "CC-PAINT": 5.0,
    "CC-E500":  7.0,
    # "CC-UNDEF" (absent) => capacité infinie côté moteur
}

ARTICLE_BOM = pd.DataFrame(
    [
        {"Parent_Article": "A100", "Child_Article": "C300", "Child_Qty": 2},
        {"Parent_Article": "A100", "Child_Article": "D400", "Child_Qty": 1},
        {"Parent_Article": "C300", "Child_Article": "X110", "Child_Qty": 1},
        {"Parent_Article": "B200", "Child_Article": "E500", "Child_Qty": 3},
        {"Parent_Article": "P777", "Child_Article": "Z900", "Child_Qty": 1},
    ]
)

def _validate_catalog_schema(df: pd.DataFrame) -> None:
    required = {"Article","Étape","Opération","Centre_de_charge","Charge_h","Semaines_Std","Semaines_AOG"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans ARTICLE_CATALOG : {sorted(missing)}")

def _validate_bom_schema(df: pd.DataFrame) -> None:
    required = {"Parent_Article","Child_Article","Child_Qty"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans ARTICLE_BOM : {sorted(missing)}")

_validate_catalog_schema(ARTICLE_CATALOG)
_validate_bom_schema(ARTICLE_BOM)
