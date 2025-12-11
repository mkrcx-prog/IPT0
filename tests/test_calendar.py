import datetime as dt
from scheduling import prochain_moment_travail, ajouter_heures_travail, retirer_heures_travail

def test_prochain_moment_travail_before_morning():
    d = dt.datetime(2026, 1, 5, 8, 0)
    r = prochain_moment_travail(d)
    assert r.time().hour == 9

def test_ajouter_heures_travail_cross_lunch():
    start = dt.datetime(2026, 1, 5, 11, 0)
    end = ajouter_heures_travail(start, 3.0)
    assert end.time().hour == 15

def test_retirer_heures_travail_cross_day():
    end = dt.datetime(2026, 1, 6, 10, 0)
    start = retirer_heures_travail(end, 8.0)
    assert start.date() == dt.date(2026, 1, 5)
