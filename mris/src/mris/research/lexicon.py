"""Phrase lexicon used to read review / audience text.

Each entry is ``(regex, polarity)`` for one assessed field.  Polarity +1 means "good for this
user" on that field (e.g. *starts immediately* for ``opening``), -1 means bad.  Matches are
negation-aware (see :mod:`mris.research.evidence`).  Flags (``slow_burn``, ``chaotic_camera``,
...) are raised by specific negative phrases and drive the hard penalties / exclusions.

The lexicon deliberately looks for the phrases the user's taste depends on ("slow first act",
"wastes no time", "talky", "shaky cam", "you need to have seen ..."), not for generic praise.
"""

from __future__ import annotations

import re

_I = re.IGNORECASE

_OPENING_WORDS = r"(?:start|opening|first act|beginning|first half|first hour|first 30 minutes|first half hour|opening act|opening stretch|early going|setup|set-up|first few minutes|first 20 minutes|first 15 minutes|first ten minutes|first 10 minutes)"

LEXICON: dict[str, list[tuple[str, int]]] = {
    "opening": [
        (r"\bstarts? (?:off )?(?:immediately|right away|with a bang|strong|fast|quickly|on a high)", 1),
        (r"\bhits the ground running", 1),
        (r"\bwastes? (?:no|little) time", 1),
        (r"\b(?:doesn'?t|does not|didn'?t|never) waste (?:any )?time", 1),
        (r"\bno time is wasted", 1),
        (
            r"\b(?:gripping|riveting|tense|thrilling|hooked|grabs you|hooks you|engaging|intense|exciting)"
            r" (?:right )?(?:from|in) the (?:very )?(?:start|get-go|first (?:scene|minute|frame)s?|opening(?: scene| minutes| moments)?|outset|beginning)",
            1,
        ),
        (
            r"\bhooks? (?:you|viewers|the audience|me)? ?(?:immediately|instantly|right away|from the start|early)",
            1,
        ),
        (
            r"\b(?:strong|gripping|explosive|thrilling|terrific|great|killer|electric|propulsive|stunning|tense|cracking|"
            r"riveting|blistering|bravura|arresting|breathless|intense|excellent|superb|fantastic|heart-pounding) "
            r"(?:opening|first act|start|opening sequence|opening scene|cold open|opening act|opening stretch|opening minutes)",
            1,
        ),
        (r"\bopens with a bang", 1),
        (r"\bfrom the (?:very )?(?:first|opening) (?:scene|minute|frame|shot|moment)s?", 1),
        (
            r"\b(?:jumps|leaps|drops you|throws you|plunges you|drops us|throws us|plunges us|dives) (?:right |straight )?into (?:the )?action",
            1,
        ),
        (r"\bin medias res", 1),
        (r"\bgets (?:right|straight) (?:down )?to (?:business|the point|it)", 1),
        (rf"\bslow {_OPENING_WORDS}", -1),
        (
            rf"\b(?:sluggish|plodding|meandering|dull|weak|boring|clunky|tedious|draggy|laborious|messy|confusing|uneventful|slow-moving) {_OPENING_WORDS}",
            -1,
        ),
        (
            r"\btakes? (?:a while|a long time|too long|forever|its time|its sweet time|some time|ages|an hour|half an hour|\d{1,3} minutes)"
            r" (?:to|before it|before) (?:get going|get started|start|kick in|get moving|find its footing|warm up|pick up|get to|get interesting|really start|heat up)",
            -1,
        ),
        (
            r"\b(?:lengthy|long|excessive|overlong|drawn-out|tedious|laborious|protracted|exposition-heavy|clunky) (?:setup|set-up|exposition|first act|opening|introduction|preamble|build-?up)",
            -1,
        ),
        (
            r"\bfirst (?:act|half|hour|30 minutes|half hour|40 minutes|45 minutes|20 minutes|third) (?:is|was|feels|felt|drags|dragged|can feel|plays) (?:a bit |rather |very |too |pretty )?(?:slow|sluggish|a slog|dull|boring|tedious|draggy|uneventful)",
            -1,
        ),
        (
            r"\b(?:drags|dragged|lags|sags) (?:early|at first|in the beginning|in the first|out of the gate)",
            -1,
        ),
        (r"\bslow to (?:start|get going|get started|build|ignite)", -1),
        (r"\btoo much (?:setup|set-up|exposition|build-?up)", -1),
        (r"\b(?:lots|a lot|plenty|loads|tons) of (?:setup|set-up|exposition)", -1),
        (
            r"\bbefore (?:anything|the action|things|the plot|the story) (?:really |actually |finally )?(?:happens|starts|kicks in|gets going|picks up)",
            -1,
        ),
        (r"\b(?:once|when) it (?:finally )?(?:gets going|picks up|kicks in)", -1),
        (r"\bpatience (?:is|will be) (?:required|rewarded)", -1),
    ],
    "pacing": [
        (
            r"\b(?:fast|brisk|breakneck|relentless|tight|propulsive|lean|taut|swift|nonstop|non-stop|zippy|rapid|frenetic|furious|tightly)[- ](?:paced|pacing|pace)",
            1,
        ),
        (r"\bnever (?:lets up|slows down|lets go|drags|sags|loses momentum|lets you breathe)", 1),
        (r"\b(?:doesn'?t|does not) (?:let up|drag|sag|slow down|outstay its welcome)", 1),
        (
            r"\b(?:edge[- ]of[- ](?:your|the)[- ]seat|white[- ]knuckle|pulse[- ]pounding|adrenaline[- ](?:fueled|fuelled|rush|soaked)|relentless|propulsive)",
            1,
        ),
        (r"\bmoves (?:along )?(?:at a )?(?:fast|brisk|quick|rapid|breakneck|good) (?:clip|pace)", 1),
        (r"\b(?:lean|tight) (?:and mean|runtime|thriller|\d+ minutes)", 1),
        (
            r"\bkeeps (?:you|the tension|things|viewers|the audience) (?:on edge|moving|going|engaged|hooked|guessing|glued)",
            1,
        ),
        (r"\b(?:flies by|zips along|breezes by|over before you know it)", 1),
        (
            r"\b(?:slow|sluggish|plodding|glacial|languid|leisurely|uneven|meandering|draggy|turgid|lethargic)[- ]?(?:paced|pacing|pace|moving)",
            -1,
        ),
        (
            r"\b(?:it|the (?:film|movie|story|middle|second act|plot)) (?:drags|dragged|sags|sagged|lags|plods|crawls)",
            -1,
        ),
        (r"\b(?:bloated|overlong|too long|padded|overstuffed|interminable)\b", -1),
        (r"\b(?:pacing|pace) (?:issues|problems|is off|is slow|suffers|is a problem|is uneven)", -1),
        (r"\b(?:boring|tedious|a slog|snooze|snoozefest|sleep-inducing|yawn-inducing)\b", -1),
        (r"\blost (?:my |our )?interest", -1),
        (r"\bslow[- ]burn(?:er|ing)?\b", -1),
    ],
    "story_clarity": [
        (
            r"\b(?:clear|simple|straightforward|clean|focused|easy-to-follow|lean) (?:story|plot|narrative|premise|objective|stakes|storytelling|goal)",
            1,
        ),
        (r"\beasy to follow", 1),
        (r"\b(?:stakes|objective|goal|mission) (?:are|is) (?:clear|simple|crystal clear)", 1),
        (
            r"\b(?:confusing|convoluted|muddled|incoherent|hard to follow|difficult to follow|overcomplicated|needlessly complicated|labyrinthine|baffling|befuddling|messy) ?(?:plot|story|narrative|script|storytelling|mess)?",
            -1,
        ),
        (r"\b(?:lost|lose|losing) track of", -1),
        (r"\b(?:makes|made) (?:little|no) sense", -1),
    ],
    "story_progression": [
        (
            r"\b(?:well|tightly|cleverly|expertly|smartly)[- ](?:plotted|structured|constructed|crafted|paced)",
            1,
        ),
        (r"\bescalat(?:es|ing|ion)\b", 1),
        (r"\bone (?:thing|set piece|twist|obstacle|complication) after another", 1),
        (r"\bkeeps (?:escalating|building|moving|raising the stakes|upping the ante)", 1),
        (r"\b(?:raises|ups) the (?:stakes|ante)", 1),
        (r"\b(?:nothing|little|not much|not a lot) (?:really )?(?:happens|going on)", -1),
        (
            r"\b(?:stalls|stalled|grinds to a halt|loses (?:steam|momentum|its way)|runs out of (?:steam|gas))",
            -1,
        ),
        (r"\b(?:episodic|repetitive|aimless|padding|filler|treading water|spins its wheels)\b", -1),
        (
            r"\b(?:second|third|final|last) act (?:sags|drags|falls apart|collapses|stumbles|fizzles|loses)",
            -1,
        ),
    ],
    "event_continuity": [
        (
            r"\b(?:constant|continuous|nonstop|non-stop|unrelenting|unceasing|wall-to-wall) (?:action|danger|tension|momentum|movement|threat|peril|thrills)",
            1,
        ),
        (r"\b(?:barely|never) (?:stops|pauses) (?:for breath|to breathe|moving)", 1),
        (r"\bmomentum\b(?! (?:stalls|drops|dies))", 1),
        (r"\b(?:long|lengthy|frequent) (?:lulls|pauses|stretches where nothing happens)", -1),
        (r"\bmomentum (?:stalls|drops|dies)", -1),
        (r"\b(?:stop-start|stop and start|start-stop)\b", -1),
    ],
    "plot_coherence": [
        (
            r"\b(?:smart|intelligent|clever|logical|coherent|airtight|plausible|credible|tight|well-written|sharp) (?:plot|script|screenplay|story|writing|thriller|plotting)",
            1,
        ),
        (r"\bcharacters (?:act|behave) (?:smart|smartly|intelligently|logically|believably|rationally)", 1),
        (
            r"\b(?:plot holes?|contrived|contrivances?|nonsensical|illogical|ridiculous plot|dumb plot|lazy (?:writing|script|plotting)|silly plot|absurd plot)\b",
            -1,
        ),
        (
            r"\b(?:idiotic|dumb|stupid|irrational|baffling|inexplicable) (?:decisions|choices|characters|behavior|behaviour|moves|plotting)",
            -1,
        ),
        (r"\bmakes no sense", -1),
        (r"\b(?:convenient|ridiculous|absurd|implausible) coincidences?", -1),
    ],
    "dialogue": [
        (
            r"\b(?:sharp|snappy|crisp|tight|punchy|efficient|economical|lean|zippy) (?:dialogue|script|writing|banter)",
            1,
        ),
        (r"\baction[- ](?:packed|heavy|filled|driven)", 1),
        (r"\b(?:more|lots of|plenty of) action(?: than talk)?", 1),
        (r"\b(?:talky|dialogue[- ]heavy|wordy|chatty|verbose|talk-heavy|dialogue-driven)\b", -1),
        (r"\btoo much (?:talking|dialogue|talk|chatter|exposition)", -1),
        (r"\b(?:lots|a lot|plenty|loads|tons) of (?:talking|dialogue|conversations?|talk)", -1),
        (
            r"\b(?:endless|long|lengthy|interminable|tedious) (?:conversations|talking|dialogue scenes|monologues?|discussions|speeches|exchanges)",
            -1,
        ),
        (r"\bpeople (?:talking|sitting) in rooms", -1),
        (r"\btalking heads\b", -1),
    ],
    "tension_continuity": [
        (
            r"\b(?:tense|taut|nail[- ]biting|gripping|suspenseful|riveting|nerve[- ](?:shredding|wracking|racking)|heart[- ]pounding|thrilling|claustrophobic|harrowing|intense)\b",
            1,
        ),
        (r"\b(?:tension|suspense) (?:never|rarely|doesn'?t) (?:lets? up|drops|lets? go|wane)", 1),
        (r"\b(?:high|real|constant|palpable|ratcheting|mounting|unbearable) (?:tension|stakes|suspense)", 1),
        (r"\bticking[- ]clock\b", 1),
        (
            r"\b(?:no|little|zero|lack of|lacks|lacking|without) (?:real )?(?:tension|suspense|stakes|urgency|thrills)",
            -1,
        ),
        (r"\b(?:tension|suspense) (?:fizzles|evaporates|dissipates|is lacking|deflates)", -1),
        (
            r"\b(?:predictable|by[- ]the[- ]numbers|paint[- ]by[- ]numbers|formulaic|run[- ]of[- ]the[- ]mill|perfunctory|uninspired)\b",
            -1,
        ),
    ],
    "action_quality": [
        (
            r"\b(?:well[- ](?:choreographed|staged|executed|shot|crafted)|thrilling|exhilarating|visceral|bone[- ]crunching|"
            r"spectacular|stellar|impressive|excellent|great|terrific|top[- ]notch|kinetic|brutal|superb|inventive|jaw[- ]dropping|"
            r"breathtaking|muscular|gritty|hard[- ]hitting) (?:action|set[- ]pieces?|fight scenes?|fights|chases?|chase sequences?|shootouts?|stunts?|stunt work|car chases?)",
            1,
        ),
        (r"\bpractical (?:stunts|effects|action)", 1),
        (
            r"\b(?:bland|forgettable|generic|uninspired|lackluster|lacklustre|dull|weak|poorly (?:shot|staged|edited)|cheap|incoherent|"
            r"choppy|sloppy) (?:action|set[- ]pieces?|fight scenes?|fights|chase scenes|chases|shootouts?|stunts?)",
            -1,
        ),
    ],
    "acting_quality": [
        (
            r"\b(?:strong|great|excellent|terrific|superb|stellar|outstanding|committed|compelling|magnetic|career[- ]best|brilliant|"
            r"fantastic|solid|convincing|charismatic|riveting|powerful|impressive|standout|towering|electric|intense|grounded|nuanced) "
            r"(?:performances?|acting|cast|turn|lead performance|ensemble|work)",
            1,
        ),
        (
            r"\b(?:acting|performances?|cast|ensemble) (?:is|are|was|were) (?:great|excellent|strong|terrific|superb|solid|top[- ]notch|fantastic|convincing|uniformly strong|first-rate)",
            1,
        ),
        (r"\b(?:carries|anchors|elevates) the (?:film|movie|material)", 1),
        (
            r"\b(?:wooden|weak|bad|poor|flat|stiff|terrible|awful|amateurish|unconvincing|phoned[- ]in|bland|lifeless|forgettable|"
            r"hammy|cringe(?:worthy|-worthy)?|charisma-free) (?:performances?|acting|cast|lead|delivery|turn|line deliveries)",
            -1,
        ),
        (
            r"\b(?:acting|performances?|cast) (?:is|are|was|were) (?:wooden|weak|bad|poor|flat|terrible|awful|amateurish|unconvincing|bland|lacking)",
            -1,
        ),
        (r"\bmiscast\b", -1),
        (r"\b(?:no|zero|little) chemistry", -1),
        (r"\bphoned it in", -1),
    ],
    "character_credibility": [
        (
            r"\b(?:believable|credible|well[- ]drawn|relatable|compelling|fleshed[- ]out|three[- ]dimensional|likable|likeable|sympathetic|grounded) (?:characters?|protagonists?|hero|lead|villain)",
            1,
        ),
        (
            r"\b(?:thin|paper[- ]thin|one[- ]dimensional|flat|cardboard|underwritten|unlikable|unlikeable|clich[eé]d|stock|thinly[- ]drawn) (?:characters?|protagonists?|hero|villain|characterization|characterisation)",
            -1,
        ),
    ],
    "cast_strength": [
        (
            r"\b(?:star[- ]studded|a[- ]list|all[- ]star|big[- ]name|heavyweight|stacked|impressive) (?:cast|stars|actors|ensemble|line-?up)",
            1,
        ),
        (r"\b(?:unknown|no[- ]name|obscure|forgettable|b-list|c-list) (?:cast|actors|stars|leads?)", -1),
    ],
    "production_quality": [
        (
            r"\b(?:slick|polished|glossy|handsome|lavish|big[- ]budget|high[- ]budget|well[- ]made|well[- ]produced|expensive[- ]looking|top[- ]notch|first[- ]rate) (?:production|production values|filmmaking|craft|thriller|blockbuster|action film|movie|film)",
            1,
        ),
        (
            r"\b(?:production values|craftsmanship|technical craft) (?:are|is) (?:high|strong|excellent|impressive|top[- ]notch)",
            1,
        ),
        (
            r"\b(?:cheap(?:ly made)?|low[- ]budget|budget constraints|shoestring|made[- ]for[- ]tv|tv[- ]movie|direct[- ]to[- ](?:video|dvd|streaming)|"
            r"straight[- ]to[- ](?:video|dvd|streaming)|bargain[- ]bin|b[- ]movie|cheap[- ]looking|(?:bad|poor|shoddy|dodgy|ropey|ropy|janky) (?:cgi|vfx|effects))",
            -1,
        ),
        (r"\b(?:feels|looks) (?:cheap|small|low[- ]budget|like a tv movie|like a made-for-tv)", -1),
        (r"\blifeless\b", -1),
    ],
    "cinematography_quality": [
        (
            r"\b(?:stunning|gorgeous|beautiful|striking|immersive|impressive|slick|stylish|crisp|handsome) (?:visuals|cinematography|photography|imagery|camerawork|camera work|lensing)",
            1,
        ),
        (r"\b(?:beautifully|well|expertly|gorgeously|handsomely|stylishly) (?:shot|photographed|lensed)", 1),
        (
            r"\b(?:ugly|murky|drab|flat|muddy|dim|washed[- ]out) (?:visuals|cinematography|photography|look|imagery|camerawork)",
            -1,
        ),
    ],
    "camera_stability": [
        (
            r"\b(?:steady|clear|clean|coherent|crisp|legible|easy to follow|fluid|controlled) (?:camera|camerawork|camera work|action|action scenes|fight choreography|editing|staging)",
            1,
        ),
        (
            r"\b(?:you can|can actually|you can actually) (?:see|follow) (?:what'?s|what is) (?:happening|going on)",
            1,
        ),
        (r"\blong takes?\b", 1),
        (
            r"\b(?:shaky[- ]?cam|shaky camera|shaky camerawork|shaky handheld|handheld chaos|nauseating|headache[- ]inducing|motion sickness|"
            r"dizzying|frenetic editing|choppy editing|chaotic editing|quick cuts|rapid[- ]fire cuts|incoherent action|hyper[- ]?kinetic|"
            r"seizure[- ]inducing|over[- ]?edited|disorienting|vertigo-inducing|swooping drone|drone shots?)",
            -1,
        ),
        (r"\bhard to (?:see|tell|follow) what'?s (?:going on|happening)", -1),
    ],
    "realism": [
        (
            r"\b(?:realistic|grounded|authentic|true[- ]to[- ]life|based on (?:a )?true (?:story|events)|real[- ]life)",
            1,
        ),
        (
            r"\b(?:over[- ]the[- ]top|cartoonish|cartoony|preposterous|far[- ]fetched|unrealistic|absurd|ludicrous|outlandish|implausible)\b",
            -1,
        ),
    ],
    "franchise": [
        (
            r"\b(?:works|stands?|functions|holds up|plays) (?:well |fine |perfectly )?(?:as|on its own as) (?:a )?stand[- ]?alone",
            1,
        ),
        (r"\b(?:don'?t|do not|doesn'?t|does not|won'?t|no) need to (?:have )?(?:seen|watch(?:ed)?|know)", 1),
        (
            r"\b(?:newcomers|new viewers|the uninitiated|first-timers) (?:can|will|should) (?:follow|enjoy|keep up)",
            1,
        ),
        (r"\bstand[- ]?alone (?:story|film|movie|thriller|adventure|entry)", 1),
        (r"\boriginal (?:story|screenplay|thriller|action film)", 1),
        (
            r"\b(?:you(?:'ll| will)? (?:need|have) to|you must|requires? (?:you|viewers|the audience) to|helps to|best if you(?:'ve)?|assumes (?:you(?:'ve)?|viewers|the audience)(?: have)?)"
            r" (?:have )?(?:seen|watch(?:ed)?|know|be familiar)",
            -1,
        ),
        (
            r"\b(?:knowledge|familiarity) (?:of|with) (?:the )?(?:previous|earlier|first|original|franchise|series|universe|lore|mythology)",
            -1,
        ),
        (r"\b(?:set|takes place|unfolds) (?:with)?in the [\w' -]{1,30}(?:universe|world|franchise|saga)", -1),
        (r"\bspin[- ]?off\b", -1),
        (r"\b(?:sequel|follow[- ]up|continuation) to\b", -1),
        (r"\bfan service\b", -1),
        (r"\b(?:fans|devotees) of the (?:franchise|series|saga|original)", -1),
    ],
}

# Negative phrases that raise flags (field, flag)
FLAG_PATTERNS: list[tuple[str, str]] = [
    (r"\bslow[- ]burn(?:er|ing)?\b", "slow_burn"),
    (
        r"\b(?:talky|dialogue[- ]heavy|wordy|too much (?:talking|dialogue|talk)|people (?:talking|sitting) in rooms|talking heads|endless conversations)",
        "excessive_dialogue",
    ),
    (
        r"\b(?:shaky[- ]?cam|shaky camera|nauseating|headache[- ]inducing|motion sickness|choppy editing|chaotic editing|frenetic editing|incoherent action|hard to (?:see|tell|follow) what'?s (?:going on|happening)|disorienting|swooping drone|drone shots?)",
        "chaotic_camera",
    ),
    (
        r"\b(?:plot holes?|contrived|nonsensical|illogical|makes no sense|(?:idiotic|dumb|stupid|irrational) (?:decisions|choices|characters|behavior|behaviour))",
        "irrational_plotting",
    ),
    (
        r"\b(?:predictable|by[- ]the[- ]numbers|paint[- ]by[- ]numbers|formulaic|generic|run[- ]of[- ]the[- ]mill|derivative)\b",
        "generic_high_concept",
    ),
    (
        r"\b(?:cheap(?:ly made)?|low[- ]budget|shoestring|made[- ]for[- ]tv|tv[- ]movie|direct[- ]to[- ](?:video|dvd)|straight[- ]to[- ](?:video|dvd)|b[- ]movie|cheap[- ]looking|(?:feels|looks) small|lifeless)\b",
        "low_production",
    ),
    (
        r"\b(?:confusing|convoluted|muddled|incoherent plot|hard to follow|difficult to follow|overcomplicated)\b",
        "confusing_story",
    ),
    (
        r"\b(?:wooden|amateurish|unconvincing|miscast|phoned[- ]in) ?(?:performances?|acting|cast|lead)?",
        "weak_cast",
    ),
]

# Story/theme traits detected in overview, keywords and review text (no polarity).
THEME_PATTERNS: dict[str, str] = {
    "heist": r"\b(?:heist|robbery|robberies|bank job|robbers?|thie(?:f|ves)|armored car|armoured car|safecracker|vault)\b",
    "rescue": r"\b(?:rescue|rescuers?|kidnapp(?:ed|ing)|abduct(?:ed|ion)|save (?:his|her|their) (?:daughter|son|family|wife|husband))\b",
    "revenge": r"\b(?:revenge|vengeance|vengeful|avenge[sd]?|avenging|vigilante|retribution)\b",
    "survival": r"\b(?:survival|survive|survivors?|stranded|trapped)\b",
    "escape": r"\b(?:escape|escapes|on the run|fugitive|breakout)\b",
    "pursuit": r"\b(?:chase|chases|pursuit|manhunt|hunted|pursued|cat-and-mouse|cat and mouse)\b",
    "police": r"\b(?:police|cops?|detectives?|fbi|swat|law enforcement|sheriff|u\.s\. marshals?)\b",
    "disaster": r"\b(?:disaster|explosion|blowout|wildfire|tornado|earthquake|tsunami|flood|collapse|catastrophe|inferno)\b",
    "offshore": r"\b(?:offshore|oil rig|drilling rig|platform at sea|saturation diver|diving support vessel|deep[- ]sea)\b",
    "industrial_disaster": r"\b(?:refinery|oil rig|drilling|mine collapse|chemical plant|industrial accident|blowout)\b",
    "time_pressure": r"\b(?:race against (?:time|the clock)|ticking[- ]clock|real[- ]time|countdown|before time runs out|within hours|one night|24 hours|oxygen (?:is )?running out)\b",
    "crime": r"\b(?:crime|criminals?|gangs?|gangsters?|cartel|mob|mafia|drug lord|syndicate|underworld|organized crime)\b",
    "hostage": r"\b(?:hostages?|held captive|hijack(?:ed|ing|ers?)?)\b",
    "ordinary_person_in_danger": r"\b(?:ordinary|everyman|average joe|innocent bystander|wrong place at the wrong time|unwitting|caught in the middle)\b",
    "immediate_danger": r"\b(?:immediate danger|from the first minute|instantly in danger|thrust into)\b",
    "protector": r"\b(?:bodyguard|protect(?:s|ing)? (?:a|the|his|her) (?:girl|boy|child|family|witness)|protector)\b",
}

# Exclusion hints read from METADATA ONLY (genres / TMDb keywords / overview) - reviews
# mention other genres in comparisons too often to be trusted for automatic rejection.
EXCLUSION_GENRES: dict[str, str] = {
    "Science Fiction": "science_fiction",
    "Fantasy": "fantasy",
    "Documentary": "documentary",
    "Music": "musical",
    "War": "military_war",
    "History": "historical_setting",
    "Animation": "animation",
    "Western": "historical_setting",
}

EXCLUSION_TEXT: dict[str, str] = {
    "science_fiction": r"\b(?:aliens?|extraterrestrial|time travel|time-travel|dystopi(?:a|an)|spaceship|starship|space station|robots?|androids?|cyborgs?|artificial intelligence|clones?|post[- ]apocalyptic|in the (?:near )?future|parallel universe|virtual reality|mutant|superheroe?s?|superpowers?)\b",
    "supernatural": r"\b(?:supernatural|ghosts?|demons?|demonic|possess(?:ed|ion)|haunt(?:ed|ing)|witch(?:es|craft)?|vampires?|zombies?|curse[ds]?|paranormal|occult|exorcis[mt]|spirits?|undead|werewol(?:f|ves))\b",
    "fantasy": r"\b(?:magic(?:al)?|wizards?|sorcer(?:er|ess|y)|dragons?|mythical|fairy tale|enchanted|elves|kingdom of)\b",
    "musical": r"\b(?:musical|sing-along)\b",
    "military_war": r"\b(?:platoon|battalion|troops|military operation|special forces mission|behind enemy lines|war zone|battlefield|combat mission|navy seals? (?:team|mission)|world war|vietnam war|military base under attack)\b",
    "political": r"\b(?:presidential|the president|white house|senator|election|congress(?:man|woman)?|political (?:thriller|conspiracy|drama)|politics|coup d'?[ée]tat|prime minister)\b",
    "historical_setting": r"\b(?:period (?:piece|drama)|victorian|medieval|\d{2}th century|ancient|civil war|cold war|prohibition era|biopic)\b",
}

PRE_2000_SETTING = re.compile(
    r"\b(?:in|during|set in|it'?s|the year|summer of|winter of|spring of|fall of|autumn of) (?:the )?(1[5-9]\d\d)s?\b"
    r"|\b(1[5-9]\d0)s\b",
    _I,
)

EXCLUDED_LANGUAGES = {
    "ko": "Korean",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "pa": "Punjabi",
    "ja": "Japanese",
    "zh": "Chinese",
    "cn": "Cantonese",
    "th": "Thai",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "tl": "Tagalog",
    "ms": "Malay",
    "es": "Spanish",
}
EXCLUDED_COUNTRIES = {"KR", "IN", "CN", "HK", "TW", "JP", "TH", "ID", "VN", "PH", "MY"}

COMPILED: dict[str, list[tuple[re.Pattern[str], int]]] = {
    field: [(re.compile(p, _I), pol) for p, pol in entries] for field, entries in LEXICON.items()
}
COMPILED_FLAGS = [(re.compile(p, _I), flag) for p, flag in FLAG_PATTERNS]
COMPILED_THEMES = {k: re.compile(p, _I) for k, p in THEME_PATTERNS.items()}
COMPILED_EXCLUSION_TEXT = {k: re.compile(p, _I) for k, p in EXCLUSION_TEXT.items()}

# Negation is checked in the same clause, within the three words before a match.
NEGATORS = re.compile(
    r"^(?:not|never|hardly|barely|isn'?t|wasn'?t|aren'?t|weren'?t|doesn'?t|don'?t|didn'?t|won'?t|without|nor|neither|"
    r"far|nothing|anything|instead|rather|lacks?|lacking)$",
    _I,
)
CLAUSE_BREAK = re.compile(r"[,;:()\u2013\u2014-]|\b(?:and|but|yet|while|although|though|whereas|so)\b", _I)

MINUTE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\btakes? (?:about |around |nearly |almost |over |more than |roughly |a good |at least |well over )?"
        r"(\d{1,3}|half an hour|an hour) ?(?:minutes|mins)? (?:to|before|for)\b",
        _I,
    ),
    re.compile(
        r"\b(?:first|opening) (\d{1,3}) ?(?:minutes|mins) (?:are|is|were|was|feel|felt|drag|dragged|of the film are)"
        r" (?:\w+ )?(?:slow|dull|boring|tedious|a slog|sluggish|uneventful|setup|set-up|exposition)",
        _I,
    ),
    re.compile(
        r"\b(\d{1,3}) ?(?:minutes|mins) (?:before|until) (?:anything|the action|the plot|things|it|the story)",
        _I,
    ),
    re.compile(
        r"\b(?:within|in) (?:the )?(?:first |opening )?(\d{1,2}) ?(?:minutes|mins)\b[^.]{0,60}"
        r"\b(?:action|explosion|chase|attack|kicks off|starts|hooked|gunfire|crash|danger|kidnap|robbery|heist)",
        _I,
    ),
]


def minutes_value(raw: str) -> float | None:
    raw = raw.lower().strip()
    if raw == "half an hour":
        return 30.0
    if raw == "an hour":
        return 60.0
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if 0 < value <= 150 else None
