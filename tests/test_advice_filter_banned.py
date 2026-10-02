"""The output filter removes every pesticide banned in India (REQ-GUARD-001)."""
import pytest

import common.advice_filter as af

# Banned for manufacture, import and use in India (CIB&RC list), plus endosulfan.
BANNED_LATIN = [
    "aldicarb", "aldrin", "benzene hexachloride", "BHC", "calcium cyanide", "chlordane",
    "copper acetoarsenite", "dibromochloropropane", "dieldrin", "endrin", "ethyl mercury chloride",
    "ethyl parathion", "heptachlor", "lindane", "maleic hydrazide", "menazone", "nitrofen",
    "paraquat dimethyl sulphate", "pentachloronitrobenzene", "pentachlorophenol",
    "phenyl mercury acetate", "sodium methane arsonate", "tetradifon", "toxaphene", "camphechlor",
    "benomyl", "carbaryl", "diazinon", "fenarimol", "fenthion", "linuron", "methyl parathion",
    "thiometon", "tridemorph", "trifluralin", "alachlor", "dichlorvos", "phorate", "phosphamidon",
    "triazophos", "trichlorfon", "endosulfan", "DDT",
]
BANNED_INDIC = [
    "एंडोसल्फान", "एन्डोसल्फान", "लिंडेन", "डीडीटी", "बीएचसी", "फोरेट", "फोरेट", "फॉस्फामिडॉन",
    "मिथाइल पैराथियान", "मिथाईल पॅराथिऑन", "ऍल्ड्रिन", "एल्ड्रिन", "डिल्ड्रिन", "क्लोरडेन",
    "ఎండోసల్ఫాన్", "లిండేన్", "డిడిటి", "ఫోరేట్", "మిథైల్ పారాథియాన్",
]
SURVIVORS = [
    "Remove weeds by hand before flowering.",
    "Endure the dry spell by mulching the soil.",
    "Children should wash hands after field work.",
    "Add compost to improve the soil.",
]


@pytest.fixture(autouse=True)
def _no_metric(monkeypatch):
    monkeypatch.setattr(af, "_cloudwatch", type("C", (), {"put_metric_data": lambda *a, **k: None})())


@pytest.mark.parametrize("name", BANNED_LATIN)
def test_banned_latin_is_detected(name):
    assert "active" in af.classify(f"Spray {name} on the cotton crop.")


@pytest.mark.parametrize("name", BANNED_INDIC)
def test_banned_indic_is_detected(name):
    assert "active" in af.classify(f"{name} फवारणी करा.")


@pytest.mark.parametrize("text", SURVIVORS)
def test_ordinary_sentences_survive(text):
    assert af.classify(text) == set()
