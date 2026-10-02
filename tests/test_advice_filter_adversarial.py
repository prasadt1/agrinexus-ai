"""
Adversarial probes for the advice filter.

The external review on 2 Oct 2026 found five sentences that classified as clean and
would have reached a farmer verbatim. They stay here as regression cases.

The probe lists below include actives and brands that were deliberately NOT added to
the filter's explicit name lists. They must be caught by the suffix fallback or the
dose patterns. When a new product name turns up in a replay or a filter miss, add it
here first: if it fails, the filter has a gap.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "common-layer" / "python"))

from common import advice_filter as af  # noqa: E402


@pytest.fixture(autouse=True)
def _no_metric(monkeypatch):
    monkeypatch.setattr(af, "_cloudwatch", type("CW", (), {"put_metric_data": lambda *a, **k: None})())


def _removed(text: str, dialect: str = "en") -> bool:
    return af.filter_advice(text, dialect, "test", add_referral=False) == ""


REVIEW_2026_10_02 = [
    "Use cartap hydrochloride granules in the maize whorl.",
    "Spray dichlorvos on the affected plants.",
    "Rogor is effective against aphids.",
    "Mix two ml per litre of water and spray.",
    "दोन मिली प्रति लिटर पाण्यात मिसळून फवारणी करा.",
]


@pytest.mark.parametrize("text", REVIEW_2026_10_02)
def test_review_findings_are_removed(text):
    assert _removed(text), text


REQUIRED_ACTIVES = [
    "Use cartap for stem borer.",
    "कार्टाप वापरा.",
    "Spray dichlorvos.",
    "डायक्लोरव्हॉस फवारा.",
    "Methomyl controls caterpillars.",
    "मेथोमिल वापरा.",
    "Chlorfenapyr works on mites.",
    "क्लोरफेनापायर वापरा.",
    "Dicofol was used against mites.",
    "डायकोफॉल फवारा.",
    "Use 2,4-D for broadleaf weeds.",
    "२,४-डी तणनाशक वापरा.",
    "Pendimethalin is a pre-emergence herbicide.",
    "पेंडीमेथालिन फवारा.",
    "Atrazine controls weeds in maize.",
    "अॅट्राझिन वापरा.",
    "Chlorothalonil protects against leaf spot.",
    "क्लोरोथॅलोनिल फवारा.",
    "Streptocycline helps against bacterial blight.",
    "स्ट्रेप्टोसायक्लिन फवारा.",
    "Validamycin controls sheath blight.",
    "व्हॅलिडामायसिन वापरा.",
    "Rogor works on aphids.",
    "रोगर फवारा.",
    "Karate is effective.",
    "कराटे फवारा.",
    "Regent granules help.",
    "रीजेंट वापरा.",
    "Lannate kills larvae.",
    "लॅनेट फवारा.",
    "Spray sulfoxaflor.",
    "Etofenprox works on hoppers.",
    "Use pymetrozine for hoppers.",
    "पायमेट्रोझिन फवारा.",
    "కార్టాప్ వాడండి.",
    "డైక్లోర్వాస్ పిచికారీ చేయండి.",
]


@pytest.mark.parametrize("text", REQUIRED_ACTIVES)
def test_required_actives_and_brands_are_removed(text):
    assert _removed(text), text


# Not in the explicit lists on purpose: caught by the suffix fallback.
UNLISTED_ACTIVES = [
    "Spray thiacloprid on the crop.",
    "Fenpropathrin controls mites.",
    "Difenoconazole is used for leaf spot.",
    "Propineb protects the leaves.",
    "Kasugamycin controls blast.",
    "Metribuzin controls weeds in soybean.",
    "Pretilachlor is used in rice.",
    "Quizalofop controls grassy weeds.",
    "Imazethapyr is used in soybean.",
    "Tolfenpyrad works on thrips.",
    "Chlorfluazuron stops larval growth.",
    "Oxydemeton is a systemic insecticide.",
    "Phenthoate controls leaf folder.",
    "Fenobucarb controls hoppers.",
    "Ethion controls mites.",
    "थायाक्लोप्रिड फवारा.",
    "फेनप्रोपाथ्रिन वापरा.",
    "डायफेनोकोनाझोल फवारा.",
    "कासुगामायसिन वापरा.",
    "फेन्थोएट फवारा.",
    "ఫెన్‌ప్రోపాత్రిన్ పిచికారీ చేయండి.",
    "డైఫెనోకోనజోల్ వాడండి.",
]


@pytest.mark.parametrize("text", UNLISTED_ACTIVES)
def test_unlisted_actives_are_caught_by_suffix(text):
    assert _removed(text), text


WORD_NUMBER_DOSES = [
    "Mix one ml in a litre of water and spray.",
    "Use half a litre per acre.",
    "Apply two kg per hectare.",
    "दो मिली प्रति लीटर पानी में मिलाकर छिड़कें।",
    "आधा लीटर प्रति एकड़ छिड़काव करें।",
    "एक मिली प्रति लिटर फवारा.",
    "अर्धा लिटर प्रति एकर वापरा.",
    "दीड मिली प्रति लिटर पाण्यात मिसळा.",
    "రెండు మి.లీ ప్రతి లీటర్ నీటిలో కలిపి పిచికారీ చేయండి.",
]


@pytest.mark.parametrize("text", WORD_NUMBER_DOSES)
def test_word_number_doses_are_removed(text):
    assert _removed(text), text


PER_AREA_DOSES = [
    "Apply 200 ml per acre.",
    "Apply 200 ml per acre with enough water.",
    "Use 2 ml per litre of water.",
    "Use 400 g per hectare.",
    "५०० मिली प्रति एकर वापरा.",
    "२५० ग्रॅम प्रति हेक्टर टाका.",
    "200 मिली प्रति एकड़ डालें।",
    "ఎకరాకు 200 మి.లీ వాడండి.",
]


@pytest.mark.parametrize("text", PER_AREA_DOSES)
def test_per_area_doses_with_use_verbs_are_removed(text):
    assert _removed(text), text


SURVIVORS = [
    "Apply 50 kg urea per acre after the first irrigation.",
    "एकरी ५० किलो युरिया वापरा.",
    "Use 20 kg seed per acre.",
    "Give 10 litres of water per plant every week.",
    "One farmer in the village saw two moths.",
    "Use yellow sticky traps.",
    "Remove two or three affected bolls per plant.",
    "पावसाळ्यात दोन वेळा पाहणी करा.",
    "रोगराई टाळण्यासाठी शेत स्वच्छ ठेवा.",
    "Carbon in the soil improves with compost.",
    "कार्बनयुक्त सेंद्रिय खत वापरा.",
    "Read the magazine article on cotton.",
    "प्रत्येक झाडाला एक लिटर पाणी द्यावे.",
    "Use 10 litres of water per plant.",
    "हर पौधे को दो लीटर पानी दें और सिंचाई का प्रयोग सुबह करें।",
]


@pytest.mark.parametrize("text", SURVIVORS)
def test_non_chemical_sentences_survive(text):
    assert af.filter_advice(text, "en", "test", add_referral=False) == text
