from enum import Enum, auto

SCREEN_W, SCREEN_H = 1280, 720
FPS    = 60
TITLE  = "Superman: Guardian of Metropolis"
WORLD_W = 4608
WORLD_H = 4608

# Only used to put a human-readable number on the off-screen event markers.
# 4 px/m makes the world 1152m across -- a plausible downtown, and it keeps
# typical readings to three digits.
PX_PER_M = 4

SKY       = (65, 110, 185)
ROAD      = (36, 38, 44)
ROAD_MRK  = (195, 172, 48)
SIDEWALK  = (76, 79, 83)
PARK      = (36, 92, 38)
WHITE     = (255, 255, 255)
BLACK     = (0,   0,   0)
BLUE_S    = (25,  55,  195)
YELLOW_S  = (255, 210, 0)
CAPE_RED  = (175, 12,  12)
RED       = (210, 35,  35)
GREEN     = (30,  160, 30)
ORANGE    = (255, 140, 0)
CYAN      = (0,   210, 235)
GRAY      = (108, 113, 118)
LGRAY     = (178, 183, 193)
DARKRED   = (108, 0,   0)
GOLD      = (252, 198, 8)
FIRE_HOT  = (255, 68,  0)
FIRE_WARM = (255, 198, 0)
ICE       = (173, 228, 255)
KRYPTO    = (0,   218, 78)
PURPLE    = (128, 0,   208)
XRAY_C    = (176, 96,  246)   # brighter than PURPLE so the HUD icon reads as clearly
                              # as the other four power colours against the dark box
SILVER    = (178, 183, 190)
DARK_GRAY = (48,  50,  56)
HUD_BG    = (8,   8,   18)
LIME      = (50,  205, 50)
DARK_BLUE = (0,   0,   100)
TEAL      = (0,   158, 158)
MAROON    = (128, 0,   0)
FLESH     = (220, 180, 140)
BROWN     = (101, 67,  33)
WATER_C   = (30,  80,  160)

BLDG_COLORS = [
    (56, 66, 76), (66, 78, 88), (46, 58, 68),
    (76, 86, 96), (53, 63, 73), (81, 91, 101),
    (41, 53, 63), (86, 96, 106),
]

class EventType(Enum):
    FIGHT_CRIMINALS = auto()
    FIGHT_ROBOTS    = auto()
    FIGHT_BRAINIAC  = auto()
    FIGHT_METALLO   = auto()
    RESCUE_FIRE     = auto()
    RESCUE_FALLING  = auto()
    RESCUE_CAR      = auto()
    RESCUE_HOSTAGE  = auto()
    ANIMAL_CAT      = auto()
    ANIMAL_FLOOD    = auto()
    FIGHT_LEX_GOONS    = auto()
    FIGHT_LEX_MECHSUIT = auto()
    RESCUE_RUBBLE      = auto()
    FIGHT_LEX_CRATES   = auto()
    FIGHT_METEOR       = auto()

EVENT_CAT = {
    EventType.FIGHT_CRIMINALS: 'fight',
    EventType.FIGHT_ROBOTS:    'fight',
    EventType.FIGHT_BRAINIAC:  'fight',
    EventType.FIGHT_METALLO:   'fight',
    EventType.RESCUE_FIRE:     'rescue',
    EventType.RESCUE_FALLING:  'rescue',
    EventType.RESCUE_CAR:      'rescue',
    EventType.RESCUE_HOSTAGE:  'rescue',
    EventType.ANIMAL_CAT:      'animal',
    EventType.ANIMAL_FLOOD:    'animal',
    EventType.FIGHT_LEX_GOONS:    'fight',
    EventType.FIGHT_LEX_MECHSUIT: 'fight',
    EventType.RESCUE_RUBBLE:      'rescue',
    EventType.FIGHT_LEX_CRATES:   'fight',
    EventType.FIGHT_METEOR:       'fight',
}

EVENT_NAMES = {
    EventType.FIGHT_CRIMINALS: "Street Criminals",
    EventType.FIGHT_ROBOTS:    "LexCorp Robot Attack!",
    EventType.FIGHT_BRAINIAC:  "Brainiac Drone Spotted!",
    EventType.FIGHT_METALLO:   "!! METALLO DETECTED !!",
    EventType.RESCUE_FIRE:     "Building Fire!",
    EventType.RESCUE_FALLING:  "Person Falling!",
    EventType.RESCUE_CAR:      "Runaway Vehicle!",
    EventType.RESCUE_HOSTAGE:  "Hostage Situation",
    EventType.ANIMAL_CAT:      "Cat Stuck in Tree",
    EventType.ANIMAL_FLOOD:    "Flooded Animal Shelter",
    EventType.FIGHT_LEX_GOONS:    "Lex Goons Incoming!",
    EventType.FIGHT_LEX_MECHSUIT: "!! LEX MECH SUIT ONLINE !!",
    EventType.RESCUE_RUBBLE:      "Collapsed Building!",
    EventType.FIGHT_LEX_CRATES:   "LexCorp Decoy Crates",
    EventType.FIGHT_METEOR:       "!! METEOR INBOUND !!",
}

EVENT_HINTS = {
    EventType.FIGHT_CRIMINALS: "SPACE=Heat Vision  F=Freeze  Q=Punch",
    EventType.FIGHT_ROBOTS:    "SPACE=Heat Vision to destroy robots!",
    EventType.FIGHT_BRAINIAC:  "F=Freeze Breath to slow the drone!",
    EventType.FIGHT_METALLO:   "Avoid the Kryptonite! Use Q=Punch!",
    EventType.RESCUE_FIRE:     "F=Freeze Breath to douse flames, then rescue citizens!",
    EventType.RESCUE_FALLING:  "Fly to the falling person to catch them!",
    EventType.RESCUE_CAR:      "Q=Super Punch the runaway car to stop it!",
    EventType.RESCUE_HOSTAGE:  "Defeat the criminals - don't hit the hostage!",
    EventType.ANIMAL_CAT:      "Fly to the tree to rescue the cat!",
    EventType.ANIMAL_FLOOD:    "F=Freeze the water and rescue all animals!",
    EventType.FIGHT_LEX_GOONS:    "SPACE=Heat Vision  F=Freeze  Q=Punch",
    EventType.FIGHT_LEX_MECHSUIT: "Dodge the missile barrage! Use Q=Punch!",
    EventType.RESCUE_RUBBLE:      "X=X-Ray Vision to find the buried, then fly to each survivor!",
    EventType.FIGHT_LEX_CRATES:   "X=X-Ray to scan, then Q=Punch the bomb. Heat vision cuts straight through!",
    EventType.FIGHT_METEOR:       "Q=Punch to crack it  -  SPACE=Heat Vision to overload it  -  F=Freeze slows the fall",
}

CAT_COLORS = {
    'fight':  (218, 38,  38),
    'rescue': (252, 152, 0),
    'animal': (48,  198, 78),
}

SCORE_TABLE = {
    EventType.FIGHT_CRIMINALS: 500,
    EventType.FIGHT_ROBOTS:    800,
    EventType.FIGHT_BRAINIAC:  1200,
    EventType.FIGHT_METALLO:   3000,
    EventType.RESCUE_FIRE:     1000,
    EventType.RESCUE_FALLING:  800,
    EventType.RESCUE_CAR:      600,
    EventType.RESCUE_HOSTAGE:  900,
    EventType.ANIMAL_CAT:      300,
    EventType.ANIMAL_FLOOD:    700,
    EventType.FIGHT_LEX_GOONS:    650,
    EventType.FIGHT_LEX_MECHSUIT: 3200,
    EventType.RESCUE_RUBBLE:      1100,
    EventType.FIGHT_LEX_CRATES:   1400,
    EventType.FIGHT_METEOR:       2000,
}

LEX_EVENT_TYPES = {
    EventType.FIGHT_ROBOTS,
    EventType.FIGHT_LEX_GOONS,
    EventType.FIGHT_LEX_MECHSUIT,
    EventType.FIGHT_LEX_CRATES,
}

LEX_INTRO_LINES = {
    EventType.FIGHT_ROBOTS:       "Rise, my LexCorp sentries. Bring me a souvenir from that alien's cape.",
    EventType.FIGHT_LEX_GOONS:    "Boys, our resident alien nuisance is nearby. Remind him whose city this is.",
    EventType.FIGHT_LEX_MECHSUIT: "Enough delegating. Time I settled this myself... suit up!",
    EventType.FIGHT_LEX_CRATES:   "Four crates, one bomb. Do try to read them properly -- the whole block is watching.",
}
LEX_DEFEAT_LINES = {
    EventType.FIGHT_ROBOTS:       "Scrap metal. I'll bill R&D for sturdier sentries.",
    EventType.FIGHT_LEX_GOONS:    "Overtime pay revoked for the lot of you. Useless.",
    EventType.FIGHT_LEX_MECHSUIT: "This isn't over, Su... I mean -- Superman. Enjoy this small victory.",
    EventType.FIGHT_LEX_CRATES:   "Lucky guess. I'll line the next one in something you can't see through either.",
}
SUPERMAN_INTRO_LINES = {
    EventType.FIGHT_ROBOTS:       "Another one of your toys, Luthor? Metropolis isn't your test lab.",
    EventType.FIGHT_LEX_GOONS:    "Paying goons again, Lex? At least give them dental.",
    EventType.FIGHT_LEX_MECHSUIT: "A mech suit? Bold move for a man allergic to a fair fight.",
    EventType.FIGHT_LEX_CRATES:   "You put a bomb in a puzzle box, Lex. That's a new low, even for you.",
}
SUPERMAN_DEFEAT_LINES = {
    EventType.FIGHT_ROBOTS:       "Back to the scrapyard, where LexCorp's ideas belong.",
    EventType.FIGHT_LEX_GOONS:    "Tell your boss Metropolis says hello.",
    EventType.FIGHT_LEX_MECHSUIT: "Suit's down, Lex. Try origami next time -- less collateral damage.",
    EventType.FIGHT_LEX_CRATES:   "No guessing involved. I just looked.",
}

# Gloat lines for events that can be failed outright. Consumed via a membership
# test in main.py, so an event only needs entries here if it has a fail state
# worth commenting on.
LEX_FAIL_LINES = {
    EventType.FIGHT_LEX_CRATES: "The lead-lined one. You always did punch first. Do enjoy the fireworks.",
}
SUPERMAN_FAIL_LINES = {
    EventType.FIGHT_LEX_CRATES: "That was the wrong box. Nobody else pays for that, Luthor.",
}

METALLO_EVENT_TYPES = {
    EventType.FIGHT_METALLO,
}

METALLO_INTRO_LINES = {
    EventType.FIGHT_METALLO: "Flesh is weak, Superman. Let's see how you handle a real monster.",
}
METALLO_DEFEAT_LINES = {
    EventType.FIGHT_METALLO: "This... isn't... over...",
}
SUPERMAN_VS_METALLO_INTRO_LINES = {
    EventType.FIGHT_METALLO: "John Corben. Still hiding behind a chunk of kryptonite?",
}
SUPERMAN_VS_METALLO_DEFEAT_LINES = {
    EventType.FIGHT_METALLO: "Go cool that core off somewhere far from Metropolis.",
}
