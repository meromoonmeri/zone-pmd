"""
palettes.py — rampes originales (sombre -> clair), inspirées de l'ambiance DS
mais recomposées : teintes décalées, valeurs relissées, 5 à 7 paliers.
"""

P = {
    # --- végétation --------------------------------------------------------
    "canopy_deep":   ["#03120c", "#071c13", "#0c2819", "#123522", "#19452b"],
    "foliage":       ["#082115", "#0e3020", "#16402a", "#1f5334", "#2b6a40", "#3c8650"],
    "foliage_lush":  ["#123320", "#1d4c2c", "#2a663a", "#3a8349", "#4fa05c", "#6cbd75"],
    "grass_meadow":  ["#153520", "#1e4828", "#2a5e31", "#38763c", "#498f49", "#5eaa5b"],
    "grass_dry":     ["#39411f", "#4d5527", "#646c2f", "#7f8639", "#9aa046", "#b6b95c"],
    "fern_teal":     ["#0a2a22", "#123c31", "#1b5342", "#256b55", "#33876b", "#46a184"],

    # --- sols --------------------------------------------------------------
    "dirt_path":     ["#3a2a1c", "#4c3823", "#61492c", "#775c37", "#8e7145", "#a68a5c"],
    "sand_pale":     ["#4f5029", "#616232", "#74753c", "#8a8a49", "#9fa059", "#b3b46e"],
    "sand_beach":    ["#8a6a34", "#a58245", "#bf9c58", "#d6b56e", "#e8cd8b", "#f6e3ad"],
    "sand_desert":   ["#7d5a2c", "#98723a", "#b28c4b", "#cba660", "#e0be7b", "#f2d69c"],
    "mud_dark":      ["#241a12", "#332618", "#453322", "#57422c", "#6b5439", "#806848"],

    # --- roche -------------------------------------------------------------
    "rock_grey":     ["#22242b", "#33363f", "#464a55", "#5c616d", "#757b86", "#9299a3"],
    "rock_warm":     ["#2d2118", "#402f21", "#55402c", "#6c5439", "#856b49", "#9f855d"],
    "rock_mossy":    ["#1c2620", "#2a382d", "#3a4d3c", "#4d654d", "#638060", "#7d9c77"],
    "cave_dark":     ["#0a0c12", "#141822", "#202634", "#2e3648", "#3f495d", "#525e74"],

    # --- eau / cristal -----------------------------------------------------
    "water_lagoon":  ["#0d3b52", "#12546f", "#18728f", "#2192ad", "#38b2c7", "#63d2dd"],
    "water_deep":    ["#07253c", "#0c3654", "#124a6f", "#1a628c", "#2a7ea8", "#45a0c4"],
    "crystal_ice":   ["#123246", "#1a4a65", "#256687", "#3487a9", "#4fa9c7", "#7fcfe2"],
    "crystal_glow":  ["#2a1440", "#3d1f5c", "#54317c", "#6f489c", "#8d64bb", "#b08bd8"],

    # --- pierre taillée / ruines -------------------------------------------
    "ruin_stone":    ["#2f2b2a", "#443f3c", "#5b554f", "#746d64", "#8f877b", "#aaa295"],
    "ruin_gold":     ["#4a3618", "#654a20", "#83632c", "#a17e3b", "#bf9b50", "#dcba6d"],
}

# ombres / lumières globales
SHADOW = "#050a08"
SUN = "#fff3c4"

BIOMES = {
    "jungle":  dict(base="canopy_deep", mid="foliage",      ground="sand_pale",
                    accent="fern_teal",  rock="rock_mossy",  water="water_lagoon"),
    "meadow":  dict(base="foliage",     mid="grass_meadow", ground="dirt_path",
                    accent="grass_dry",  rock="rock_grey",   water="water_lagoon"),
    "beach":   dict(base="water_deep",  mid="sand_beach",   ground="sand_pale",
                    accent="grass_dry",  rock="rock_warm",   water="water_lagoon"),
    "cave":    dict(base="cave_dark",   mid="rock_grey",    ground="mud_dark",
                    accent="crystal_ice", rock="rock_grey",  water="water_deep"),
    "crystal": dict(base="cave_dark",   mid="crystal_ice",  ground="rock_grey",
                    accent="crystal_glow", rock="rock_grey", water="water_deep"),
    "desert":  dict(base="rock_warm",   mid="sand_desert",  ground="sand_beach",
                    accent="grass_dry",  rock="rock_warm",   water="water_lagoon"),
    "ruins":   dict(base="foliage",     mid="ruin_stone",   ground="ruin_gold",
                    accent="rock_mossy", rock="ruin_stone",  water="water_lagoon"),
}
