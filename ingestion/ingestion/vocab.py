"""Контролирани речници за класификацията на наборите (fail-closed).

Профилът (``spec/dcat-ap/profile.json``) обявява кои полета ползват контролирани речници на ЕС.
Дотук тези полета бяха свободни низове — печатна грешка като ``HEALTH`` вместо ``HEAL`` минаваше
валидацията и произвеждаше счупен DCAT URI. Тук ги закотвяме към каноничните кодове и отхвърляме
непознати стойности при приемане, за да е класификацията машинно съгласувана от ден 1.

Източници (authority tables на Publications Office на ЕС):
- data-theme:   http://publications.europa.eu/resource/authority/data-theme
- frequency:    http://publications.europa.eu/resource/authority/frequency
- access-right: http://publications.europa.eu/resource/authority/access-right
- NUTS (BG):    https://ec.europa.eu/eurostat/web/nuts
"""

from __future__ import annotations

import re

# Пълният набор кодове от authority-таблицата data-theme (здравето е ``HEAL``).
DATA_THEMES: frozenset[str] = frozenset(
    {
        "AGRI",
        "ECON",
        "EDUC",
        "ENER",
        "ENVI",
        "GOVE",
        "HEAL",
        "INTR",
        "JUST",
        "REGI",
        "SOCI",
        "TECH",
        "TRAN",
        "OP_DATPRO",
    }
)

# Често използваните кодове за честота на актуализация (accrual periodicity).
FREQUENCIES: frozenset[str] = frozenset(
    {
        "ANNUAL",
        "ANNUAL_2",
        "ANNUAL_3",
        "BIENNIAL",
        "TRIENNIAL",
        "MONTHLY",
        "MONTHLY_2",
        "MONTHLY_3",
        "BIMONTHLY",
        "WEEKLY",
        "WEEKLY_2",
        "WEEKLY_3",
        "BIWEEKLY",
        "QUARTERLY",
        "DAILY",
        "DAILY_2",
        "CONT",
        "UPDATE_CONT",
        "IRREG",
        "NEVER",
        "UNKNOWN",
        "OTHER",
    }
)

# Права за достъп (access-right).
ACCESS_RIGHTS: frozenset[str] = frozenset({"PUBLIC", "RESTRICTED", "NON_PUBLIC"})

# Лицензи, които порталът поддържа, с каноничен URI. Това е единственият източник на истина за
# лицензите — DCAT изграждането (``dcat/build.py``, ``collections.py``) внася оттук, така че всеки
# позволен лиценз задължително има URI и обратно.
LICENSE_URI: dict[str, str] = {
    "CC-BY-4.0": "http://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "http://creativecommons.org/licenses/by-sa/4.0/",
    "CC0-1.0": "http://creativecommons.org/publicdomain/zero/1.0/",
}
LICENSES: frozenset[str] = frozenset(LICENSE_URI)

# NUTS кодове за България: ``BG`` (държава) и подрегионите ``BG3``, ``BG31``, ``BG311``…
_NUTS_BG = re.compile(r"BG[0-9]{0,3}")


def _reject(value: str, allowed: frozenset[str], field: str) -> str:
    options = ", ".join(sorted(allowed))
    raise ValueError(f"{field}: непознат код '{value}'. Позволени: {options}")


def check_theme(codes: list[str]) -> list[str]:
    for code in codes:
        if code not in DATA_THEMES:
            _reject(code, DATA_THEMES, "theme")
    return codes


def check_frequency(code: str | None) -> str | None:
    if code is not None and code not in FREQUENCIES:
        _reject(code, FREQUENCIES, "accrual_periodicity")
    return code


def check_access_right(code: str) -> str:
    if code not in ACCESS_RIGHTS:
        _reject(code, ACCESS_RIGHTS, "access_rights")
    return code


def check_license(code: str) -> str:
    if code not in LICENSES:
        _reject(code, LICENSES, "license")
    return code


def check_spatial(codes: list[str]) -> list[str]:
    for code in codes:
        if not _NUTS_BG.fullmatch(code):
            raise ValueError(
                f"spatial: '{code}' не е валиден NUTS код за България "
                f"(очаква се 'BG' или 'BG'+цифри, напр. BG34, BG411)"
            )
    return codes
