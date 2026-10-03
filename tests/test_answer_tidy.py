"""
The filter tidies what the model writes around the advice: Markdown bold, an opening
"I cannot recommend pesticides" on a question that asked for none, and the model's own
closing KVK referral, which the footer repeats.
"""
import glob
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import advice_filter as af  # noqa: E402
from common import district_helplines as dh  # noqa: E402

REPLAY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "try", "replays")

QUESTION = "How do I control whitefly on cotton?"

# WhatsApp reply to the visitor sample question "Whitefly on cotton", live phone test,
# 3 October 2026, as the model wrote it (before the footer).
LIVE_WHITEFLY = (
    "I cannot recommend specific pesticide names or doses, but here are non-chemical steps you can take:\n\n"
    "**Start with cultural practices:** Sow cotton on time (by 15th May for hirsutum hybrids, 30th April for "
    "Desi varieties). Keep your field and bunds weed-free, especially weeds like kanghi buti and congress grass "
    "which host whitefly. Plant two rows of sorghum, pearl-millet, or maize around your cotton field as a border crop.\n\n"
    "**Monitor early:** Install yellow sticky traps (20–40 per acre) from July–August to catch whiteflies early. "
    "Use vacuum suction pumps in August if the population is high. Spray neem oil twice in the early crop stage "
    "(up to 60 days after sowing).\n\n"
    "**Avoid these mistakes:** Do not use pyrethroids or organophosphates before 120 days, and never mix "
    "insecticides. Excessive nitrogen fertilizer also attracts whitefly.\n\n"
    "For chemical control options, contact your local KVK (Krishi Vigyan Kendra) for the correct product and "
    "application rate."
)

MODEL_REFERRAL = "For chemical control options, contact your local KVK (Krishi Vigyan Kendra)"
FOOTER_EN = dh.REFERRAL_LINES["answer"]["en"]


@pytest.fixture(autouse=True)
def _no_metrics(monkeypatch):
    monkeypatch.setattr(af, "_emit_metric", lambda *_a, **_k: None)


def _whatsapp(text, question=QUESTION, **kw):
    return af.filter_advice(text, "en", "whatsapp_text", question=question, **kw)


class TestLiveWhiteflyAnswer:
    def test_whatsapp_reply(self):
        out = _whatsapp(LIVE_WHITEFLY)
        assert out.startswith("Here are non-chemical steps you can take:\n\n*Start with cultural practices:* Sow cotton")
        assert "I cannot recommend" not in out
        assert "**" not in out
        assert "*Monitor early:* Install" in out and "*Avoid these mistakes:* Do not" in out
        assert MODEL_REFERRAL not in out
        assert out.count("KVK") == 1 and FOOTER_EN in out
        assert out.rstrip().endswith("1800-180-1551")

    def test_advice_itself_is_untouched(self):
        out = _whatsapp(LIVE_WHITEFLY)
        for sentence in (
            "Plant two rows of sorghum, pearl-millet, or maize around your cotton field as a border crop.",
            "Install yellow sticky traps (20–40 per acre) from July–August to catch whiteflies early.",
            "Spray neem oil twice in the early crop stage (up to 60 days after sowing).",
            "Excessive nitrogen fertilizer also attracts whitefly.",
        ):
            assert sentence in out

    def test_web_chat_shows_text_as_typed_so_gets_no_markers(self):
        out = af.filter_advice(LIVE_WHITEFLY, "en", "web_text", question=QUESTION)
        assert "*" not in out
        assert "Start with cultural practices: Sow cotton" in out


class TestRefusalOpener:
    def test_kept_when_the_question_asks_for_a_pesticide(self):
        out = _whatsapp(LIVE_WHITEFLY, question="Which spray for whitefly on cotton?")
        assert out.startswith("I cannot recommend specific pesticide names or doses, but here are")

    def test_kept_when_no_question_is_passed(self):
        out = af.filter_advice(LIVE_WHITEFLY, "en", "whatsapp_text")
        assert out.startswith("I cannot recommend specific pesticide names or doses")

    @pytest.mark.parametrize(
        "opener, rest",
        [
            ("I can't give pesticide names or quantities. ", "Keep the field weed-free."),
            ("I can’t recommend any insecticide; however, ", "keep the field weed-free."),
            ("I cannot recommend pesticides, fungicides or doses, but ", "keep the field weed-free."),
            ("I am unable to recommend chemical products.\n\n", "Keep the field weed-free."),
            ("We do not recommend specific pesticides. Instead, ", "keep the field weed-free."),
        ],
    )
    def test_other_wordings(self, opener, rest):
        out = _whatsapp(opener + rest, add_referral=False)
        assert out == "Keep the field weed-free."

    def test_a_reply_that_is_only_the_refusal_stays(self):
        text = "I cannot recommend specific pesticide names or doses."
        assert _whatsapp(text, add_referral=False) == text

    def test_the_fixed_policy_reply_stays(self):
        # Sent only for a pesticide question; checked here even against a plain question.
        policy = af.pesticide_policy("en")
        assert _whatsapp(policy, question="Which pesticide for whitefly?", add_referral=False) == policy

    @pytest.mark.parametrize(
        "text",
        [
            "I recommend removing affected leaves. Do not use chemical sprays near water.",
            "Remove affected leaves. I cannot recommend pesticides, but traps help.",
            "Whitefly cannot be controlled by one method alone. Keep the field weed-free.",
        ],
    )
    def test_ordinary_first_sentences_stay(self, text):
        assert _whatsapp(text, add_referral=False) == text


class TestModelReferral:
    def test_dropped_before_a_source_line(self):
        text = "Remove affected leaves.\n\n" + MODEL_REFERRAL + " for the correct product.\n\nSource: Cotton IPM Guide"
        out = _whatsapp(text)
        assert MODEL_REFERRAL not in out
        assert "Remove affected leaves." in out and "Source: Cotton IPM Guide" in out
        assert out.count("KVK") == 1 and FOOTER_EN in out

    def test_dropped_from_the_end_of_a_paragraph(self):
        out = _whatsapp("Remove affected leaves. Install yellow sticky traps. " + MODEL_REFERRAL + " for the right product.")
        assert out.startswith("Remove affected leaves. Install yellow sticky traps.\n\n" + FOOTER_EN)

    def test_kept_when_no_footer_follows(self):
        text = "Remove affected leaves. " + MODEL_REFERRAL + " for the right product."
        assert _whatsapp(text, add_referral=False) == text

    def test_a_reply_that_is_only_the_referral_stays(self):
        text = MODEL_REFERRAL + " for the right product."
        assert _whatsapp(text).startswith(text)

    @pytest.mark.parametrize(
        "last",
        [
            "Take a soil sample to your nearest KVK for testing.",
            "Contact your local KVK for advice on improving cotton production.",
            "KVK scientists advise against spraying pesticide during flowering.",
            "Ask your KVK about certified seed.",
        ],
    )
    def test_other_closing_sentences_about_the_kvk_stay(self, last):
        out = _whatsapp("Remove affected leaves. " + last)
        assert last in out

    @pytest.mark.parametrize(
        "dialect, last",
        [
            ("mr", "रासायनिक नियंत्रणासाठी तुमच्या जवळच्या कृषी विज्ञान केंद्राशी (KVK) संपर्क साधा."),
            ("mr", "रासायनिक नियंत्रणासाठी तुमच्या जवळच्या कृषी विज्ञान केंद्राशी संपर्क साधावा."),
        ],
    )
    def test_marathi_referrals_seen_in_the_replays(self, dialect, last):
        body = "पिवळे चिकट सापळे शेतात लावा. शेताची स्वच्छता राखा."
        out = af.filter_advice(body + " " + last, dialect, "whatsapp_photo", kind="photo")
        assert last not in out
        assert out.startswith(body + "\n\n" + dh.REFERRAL_LINES["photo"][dialect])

    def test_replays_lose_only_closing_referrals(self):
        dropped = set()
        for path in sorted(glob.glob(os.path.join(REPLAY_DIR, "*.json"))):
            with open(path, encoding="utf-8") as f:
                for r in json.load(f)["results"]:
                    for key in ("recommendations", "reply_text"):
                        text = r.get(key)
                        if not text:
                            continue
                        kept = af._drop_model_referral(text)
                        assert text.startswith(kept)
                        if kept != text:
                            dropped.add(text[len(kept):].strip())
        assert dropped
        for sentence in dropped:
            assert sentence.startswith("रासायनिक नियंत्रणासाठी") and "कृषी विज्ञान केंद्राशी" in sentence


class TestMarkup:
    def test_whatsapp_bold_is_left_alone(self):
        text = "*Problem:* whitefly\n*Steps:* Remove affected leaves."
        assert af.filter_advice(text, "en", "whatsapp_photo", kind="photo", add_referral=False) == text

    def test_markdown_bold_becomes_whatsapp_bold(self):
        out = af.filter_advice("**Problem:** whitefly. Use **yellow** traps.", "en", "whatsapp_text", add_referral=False)
        assert out == "*Problem:* whitefly. Use *yellow* traps."

    def test_devanagari(self):
        out = af.filter_advice("**पहिले पाऊल:** बाधित पाने काढा.", "mr", "whatsapp_text", add_referral=False)
        assert out == "*पहिले पाऊल:* बाधित पाने काढा."

    def test_bold_label_still_counts_as_a_label_when_a_dose_is_removed(self):
        text = "**Steps:** Remove affected leaves. Spray profenofos 50% EC at 2 ml per litre of water."
        out = af.filter_advice(text, "en", "whatsapp_text", add_referral=False)
        assert out == "*Steps:* Remove affected leaves."
