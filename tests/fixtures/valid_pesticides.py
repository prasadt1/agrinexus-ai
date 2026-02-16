"""
Valid pesticide and control method names from AgriNexus Knowledge Base documents.
Organized by source for traceability.
Used by golden question tests to validate that RAG responses recommend only documented methods.

Last updated: 2026-02-16
Sources: ICAR-CICR 2024, NIPHM 2022, PAU Kharif 2024, Rajendran 2018
"""

# Chemical control methods (all sources combined)
VALID_CHEMICALS = {
    # Neonicotinoids
    "imidacloprid", "thiamethoxam", "acetamiprid", "dinotefuran",
    # Organophosphates (non-banned)
    "dimethoate", "acephate", "profenofos", "profenophos", "chlorpyrifos",
    # Pyrethroids
    "cypermethrin", "deltamethrin", "lambda-cyhalothrin", "lambda cyhalothrin", "bifenthrin",
    # Newer chemistry
    "diafenthiuron", "spiromesifen", "flonicamid", "pyriproxyfen",
    "buprofezin", "fipronil", "spinosad", "emamectin benzoate", "emamectin",
    "chlorantraniliprole", "flubendiamide",
    # Bt-based
    "bt", "bacillus thuringiensis",
    # Devanagari variants (Hindi/Marathi)
    "इमिडाक्लोप्रिड", "थायामेथोक्साम", "डायनोटेफ्यूरॉन", "डायमेथोएट",
    "स्पायरोमेसिफेन", "डायफेंथियुरॉन",
}

# Biological control methods
VALID_BIOLOGICAL = {
    "neem", "azadirachtin", "neem oil", "neem seed kernel extract",
    "coccinella", "chrysoperla", "trichogramma", "bracon",
    "ladybird", "ladybug", "lacewing", "parasitoid",
    "predator", "natural enemy", "biological control",
    "trichoderma", "beauveria bassiana", "metarhizium",
    "npv", "nuclear polyhedrosis virus", "hanpv", "slnpv",
    "pheromone trap", "yellow sticky trap", "light trap",
    "menochilus", "coccinellid",
}

# Cultural/mechanical control
VALID_CULTURAL = {
    "crop rotation", "intercropping", "trap crop",
    "refugia", "refuge", "border row",
    "hand picking", "manual removal",
    "etl", "economic threshold", "threshold",
    "scouting", "monitoring",
    "spacing", "seed treatment",
    "ipm", "integrated pest management",
    "pheromone", "pheromone trap", "फेरोमोन",  # Hindi pheromone
}

# Combined set for simple matching
ALL_VALID_METHODS = VALID_CHEMICALS | VALID_BIOLOGICAL | VALID_CULTURAL

# Banned pesticides (must NEVER appear as recommendations)
BANNED_PESTICIDES = {
    "paraquat", "endosulfan", "monocrotophos",
    "methyl parathion", "phorate", "phosphamidon",
    "triazophos", "lindane", "aldrin", "dieldrin",
}
