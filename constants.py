from enum import Enum, auto

SCREEN_W, SCREEN_H = 1280, 720
FPS    = 60
TITLE  = "Superman: Guardian of Metropolis"
WORLD_W = 4608
WORLD_H = 4608

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
}

LEX_EVENT_TYPES = {
    EventType.FIGHT_ROBOTS,
    EventType.FIGHT_LEX_GOONS,
    EventType.FIGHT_LEX_MECHSUIT,
}

LEX_INTRO_LINES = {
    EventType.FIGHT_ROBOTS:       "Rise, my LexCorp sentries. Bring me a souvenir from that alien's cape.",
    EventType.FIGHT_LEX_GOONS:    "Boys, our resident alien nuisance is nearby. Remind him whose city this is.",
    EventType.FIGHT_LEX_MECHSUIT: "Enough delegating. Time I settled this myself... suit up!",
}
LEX_DEFEAT_LINES = {
    EventType.FIGHT_ROBOTS:       "Scrap metal. I'll bill R&D for sturdier sentries.",
    EventType.FIGHT_LEX_GOONS:    "Overtime pay revoked for the lot of you. Useless.",
    EventType.FIGHT_LEX_MECHSUIT: "This isn't over, Su... I mean -- Superman. Enjoy this small victory.",
}
SUPERMAN_INTRO_LINES = {
    EventType.FIGHT_ROBOTS:       "Another one of your toys, Luthor? Metropolis isn't your test lab.",
    EventType.FIGHT_LEX_GOONS:    "Paying goons again, Lex? At least give them dental.",
    EventType.FIGHT_LEX_MECHSUIT: "A mech suit? Bold move for a man allergic to a fair fight.",
}
SUPERMAN_DEFEAT_LINES = {
    EventType.FIGHT_ROBOTS:       "Back to the scrapyard, where LexCorp's ideas belong.",
    EventType.FIGHT_LEX_GOONS:    "Tell your boss Metropolis says hello.",
    EventType.FIGHT_LEX_MECHSUIT: "Suit's down, Lex. Try origami next time -- less collateral damage.",
}
