"""Traductions de l'interface."""

from spoolmanager.i18n import current_language, set_language, t


def test_default_language_is_french():
    set_language("fr")
    assert current_language() == "fr"
    assert t("tab.settings") == "Réglages"
    assert t("tab.dashboard") == "Tableau de bord"


def test_english_translations():
    set_language("en")
    assert t("tab.settings") == "Settings"
    assert t("tab.dashboard") == "Dashboard"
    assert t("settings.language") == "Interface language"
    assert t("history.filter.review") == "To review"


def test_unknown_language_falls_back_to_french():
    set_language("de")
    assert current_language() == "fr"
    assert t("tab.settings") == "Réglages"


def test_format_placeholders():
    set_language("en")
    assert t("printer.slot", slot=2) == "Slot 2"
    set_language("fr")
    assert t("printer.slot", slot=2) == "Emplacement 2"
