"""
TimeLapse Pro — AI Tag Vocabulary Manager
==========================================
Selvudvidende tag-vokabular til billed-analyse.

Princip:
  - Starter med ~300 foruddefinerede tags organiseret i kategorier
  - Vision-modellen bruger listen som udgangspunkt
  - Nye tags modellen finder gemmes automatisk med approved=False
  - Admin kan godkende/afvise nye tags i UI
  - Godkendte tags indgår i næste prompt → vokabularet vokser

DB-tabel: ai_tag_vocabulary (PostgreSQL)
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ── Foruddefineret startvokabular ─────────────────────────────────────────────
# ENGELSK kanonisk — dette er hvad AI-modellen bruger i prompten OG hvad der
# lagres på captures (Capture.ai_tags). Dansk visningsnavn er i
# PREDEFINED_DA_LABELS nedenfor, og bruges til display_name_da ved seeding.
# Organiseret i kategorier. Alle tags engelsk, lowercase, underscore.
#
# HISTORIK: Før dette var tags danske (se CANONICAL_TAG_OVERRIDES nedenfor,
# som stadig bruges til at korrelere GAMLE danske tags allerede på captures).

PREDEFINED_TAGS: dict[str, list[str]] = {

    "structures": [
        "foundation", "basement", "ground_floor", "floor_1", "floor_2", "floor_3",
        "attic_floor", "roof", "flat_roof", "pitched_roof", "facade", "gable",
        "concrete_wall", "brick_wall", "wood_wall", "glass_facade", "column", "beam",
        "floor_slab", "stairs", "elevator_shaft", "chimney", "balcony", "terrace",
        "carport", "garage", "basement_entrance", "light_well", "roof_dormer",
        "window_section", "door", "gate", "garden_gate", "fence", "wall",
    ],

    "building_types": [
        "single_family_house", "townhouse", "apartment_building", "villa", "summer_house",
        "commercial_building", "office_building", "warehouse", "factory", "industrial_hall",
        "parking_garage", "shed", "pavilion", "container_housing",
        "historic_building", "church", "school", "institution",
    ],

    "construction_progress": [
        "empty_lot", "excavation", "earthworks", "piling",
        "foundation_pour", "basement_cast", "concrete_slab_cast",
        "shell_construction", "shell_complete", "bricklaying",
        "roof_structure", "roof_covering", "roofing_felt", "roof_tiles",
        "facade_cladding", "plastering", "wall_insulation",
        "window_installation", "door_installation", "interior_fitting",
        "electrical_installation", "plumbing_installation", "flooring",
        "interior_painting", "exterior_painting", "tiling",
        "bathroom_installation", "kitchen_installation", "completed_building",
        "renovation", "demolition", "extension", "remodeling",
    ],

    "heavy_machinery": [
        "tower_crane", "mobile_crane", "mini_crane", "excavator",
        "mini_excavator", "bulldozer", "loader", "wheel_loader",
        "concrete_mixer_truck", "concrete_pump", "concrete_vibrator_truck", "asphalt_paver",
        "road_grader", "road_roller", "compactor", "drilled_pile_rig",
        "pile_driver", "sheet_pile_machine",
    ],

    "equipment_and_tools": [
        "scaffolding", "rolling_scaffold", "work_platform", "scissor_lift",
        "telescopic_lift", "forklift", "hand_truck", "wheelbarrow",
        "concrete_mixer", "compressor", "generator", "welding_equipment",
        "hammer_drill", "angle_grinder", "trestle", "construction_hoist",
        "concrete_formwork", "formwork", "tension_strap", "crane_hook",
        "lifting_gear", "ladder", "pallet", "storage_container",
        "waste_container", "dumpster", "water_tank", "diesel_tank",
    ],

    "vehicles": [
        "car", "van", "large_van", "pickup_truck",
        "truck", "truck_with_crane", "dump_truck", "semi_trailer",
        "tanker_truck", "concrete_transport_truck", "dolly_trailer", "trailer",
        "ambulance", "fire_truck", "police_car", "bus", "minibus",
        "motorcycle", "moped", "bicycle", "e_bike", "e_scooter",
        "industrial_truck", "pallet_jack",
    ],

    "materials_on_site": [
        "rebar", "reinforcement_bars", "concrete_blocks", "lightweight_concrete_blocks",
        "bricks", "aerated_concrete", "concrete_elements", "prefab_elements",
        "steel_beams", "steel_plates", "steel_pipes", "wood_planks",
        "plywood", "roof_tiles", "roofing_felt_rolls", "insulation_panels",
        "mineral_wool", "gypsum_boards", "windows_on_pallet", "doors_on_pallet",
        "plumbing_pipes", "cables", "cable_conduit", "sand", "gravel", "stone",
        "soil", "fill_sand", "concrete_mix", "mortar", "adhesive_bags",
        "paint_buckets", "waste_bags", "pallets", "stacked_materials",
    ],

    "workers_and_activity": [
        "worker", "multiple_workers", "group_of_workers",
        "worker_active", "worker_break", "worker_climbing",
        "helmet", "orange_vest", "yellow_vest", "safety_equipment",
        "safety_shoes", "safety_glasses", "hearing_protection",
        "welder", "bricklayer", "carpenter", "electrician", "plumber",
        "crane_operator", "machine_operator", "site_foreman", "supervisor",
        "no_activity", "active_construction_site", "quiet_construction_site",
    ],

    "weather": [
        "sunshine", "partly_cloudy", "overcast", "gray_sky",
        "fog", "light_fog", "thick_fog", "haze", "rain", "light_rain",
        "heavy_rain", "downpour", "hail", "snow", "light_snow",
        "heavy_snowfall", "snow_on_ground", "ice", "frost",
        "hoarfrost", "windy", "storm", "thunder", "rainbow",
        "cloud_cover", "blue_sky", "white_clouds", "clear_sky",
        "low_cloud_cover", "high_sun", "low_sun",
    ],

    "light_and_time": [
        "daylight", "sunny_day", "dark_day", "dawn",
        "dusk", "night", "artificial_lighting", "work_light",
        "backlight", "direct_sunlight", "diffuse_light", "shadow",
        "long_shadow", "short_shadow", "golden_light", "blue_light",
        "clear_sunlight", "sun_in_lens", "glare", "lens_flare",
        "distracting_glare", "good_timelapse_lighting",
    ],

    "safety_and_barriers": [
        "construction_site_fence", "green_construction_fence", "construction_site_gate",
        "no_access_sign", "warning_sign", "road_sign",
        "safety_net", "edge_protection", "barrier",
        "warning_tape", "traffic_cones", "road_diversion", "fire_extinguisher",
        "first_aid_cabinet", "emergency_exit_sign",
    ],

    "site_condition": [
        "tidy_site", "messy_site", "very_messy",
        "muddy_ground", "dry_ground", "wet_ground",
        "snow_covered", "ice_covered", "dusty", "mud",
        "puddles", "flooding", "erosion",
    ],

    "surroundings": [
        "road", "sidewalk", "asphalt", "pavement_tiles", "grass", "garden",
        "tree", "trees", "bush", "hedge", "nature", "field",
        "forest", "lake", "stream", "canal", "harbor",
        "neighboring_building", "neighbor_renovation", "parking",
        "lamp_post", "electrical_cabinet", "manhole_cover", "ditch",
    ],

    "gdpr_safe": [
        "license_plate_visible", "person_visible", "face_visible",
        "group_of_people", "pedestrian", "cyclist",
    ],

    "anomalies_and_events": [
        "fire", "smoke", "flames", "fire_hazard",
        "water_damage", "flood_risk", "cloudburst",
        "structural_damage", "crack", "collapse_risk",
        "new_object", "missing_object", "unknown_object",
        "abandoned_equipment", "theft_risk", "vandalism",
        "unauthorized_person", "animal_on_site",
        "crane_alarm", "accident", "safety_incident",
    ],

    "animals": [
        "dog", "cat", "bird", "flock_of_birds", "seagull",
        "rat", "fox", "hare",
    ],

    "camera_quality": [
        "clear_image", "foggy_image", "dirty_lens",
        "condensation_on_lens", "obstruction_in_front_of_camera",
        "overexposed", "underexposed", "correct_exposure",
        "motion_blur", "incorrect_focus", "night_image_ok",
        "night_image_too_dark", "camera_moved", "blown_highlights",
        "flare", "low_contrast",
    ],

    "change_detection": [
        "new_construction_since_last", "progress_since_last",
        "new_vehicle", "new_machine", "new_container",
        "materials_removed", "construction_removed",
        "crane_position_changed", "new_floor_visible",
        "roof_started", "facade_changed",
        "no_change", "small_change", "large_change",
    ],
}

# ── Dansk visningsnavn pr. engelsk tag ────────────────────────────────────────
# Bruges KUN til at udfylde display_name_da ved seeding af PREDEFINED_TAGS.
# AI-foreslåede oversættelser for NYE tags (model-opfundne) håndteres separat
# via new_tags_da i record_usage() — denne dict er for det statiske startvokabular.
PREDEFINED_DA_LABELS: dict[str, str] = {
    # structures
    "foundation": "fundament", "basement": "kælder", "ground_floor": "stueetage",
    "floor_1": "etage 1", "floor_2": "etage 2", "floor_3": "etage 3",
    "attic_floor": "tagetage", "roof": "tag", "flat_roof": "fladt tag",
    "pitched_roof": "skråt tag", "facade": "facade", "gable": "gavl",
    "concrete_wall": "betonvæg", "brick_wall": "murstensvæg", "wood_wall": "trævæg",
    "glass_facade": "glasfacade", "column": "søjle", "beam": "bjælke",
    "floor_slab": "dæk", "stairs": "trappe", "elevator_shaft": "elevatorskakt",
    "chimney": "skorsten", "balcony": "balkon", "terrace": "terrasse",
    "carport": "carport", "garage": "garage", "basement_entrance": "kælder nedgang",
    "light_well": "lyskasse", "roof_dormer": "tagkvist", "window_section": "vinduesparti",
    "door": "dør", "gate": "port", "garden_gate": "havelåge", "fence": "hegn", "wall": "mur",
    # building_types
    "single_family_house": "enfamiliehus", "townhouse": "rækkehus",
    "apartment_building": "etagebyggeri", "villa": "villa", "summer_house": "sommerhus",
    "commercial_building": "erhvervsbygning", "office_building": "kontorhus",
    "warehouse": "lager", "factory": "fabrik", "industrial_hall": "hal",
    "parking_garage": "parkeringshus", "shed": "skur", "pavilion": "pavillon",
    "container_housing": "containerbolig", "historic_building": "historisk bygning",
    "church": "kirke", "school": "skole", "institution": "institution",
    # construction_progress
    "empty_lot": "tom grund", "excavation": "udgravning", "earthworks": "jordarbejde",
    "piling": "pilotering", "foundation_pour": "fundamentstøbning",
    "basement_cast": "kælder støbt", "concrete_slab_cast": "betondæk støbt",
    "shell_construction": "råhus opførelse", "shell_complete": "råhus færdigt",
    "bricklaying": "murerarbejde", "roof_structure": "tagkonstruktion",
    "roof_covering": "tagdækning", "roofing_felt": "tagpap", "roof_tiles": "tagsten",
    "facade_cladding": "facadebeklædning", "plastering": "puds",
    "wall_insulation": "isolering ydervæg", "window_installation": "vinduesmontage",
    "door_installation": "dørmontage", "interior_fitting": "indvendig aptering",
    "electrical_installation": "el-installation", "plumbing_installation": "vvs-installation",
    "flooring": "gulvlægning", "interior_painting": "maling indvendig",
    "exterior_painting": "maling udvendig", "tiling": "flisearbejde",
    "bathroom_installation": "badeværelse montage", "kitchen_installation": "køkken montage",
    "completed_building": "færdigbygget", "renovation": "renovering",
    "demolition": "nedrivning", "extension": "tilbygning", "remodeling": "ombygning",
    # heavy_machinery
    "tower_crane": "tårnkran", "mobile_crane": "mobilkran", "mini_crane": "minikran",
    "excavator": "gravemaskine", "mini_excavator": "minigraver", "bulldozer": "bulldozer",
    "loader": "læssemaskine", "wheel_loader": "hjullæsser",
    "concrete_mixer_truck": "betonbil", "concrete_pump": "betonpumpe",
    "concrete_vibrator_truck": "vibratorbil", "asphalt_paver": "asfaltmaskine",
    "road_grader": "vejhøvl", "road_roller": "tromle", "compactor": "komprimator",
    "drilled_pile_rig": "borepælemaskine", "pile_driver": "pæleramme",
    "sheet_pile_machine": "spunsvægsmaskine",
    # equipment_and_tools
    "scaffolding": "stillads", "rolling_scaffold": "rullestillads",
    "work_platform": "arbejdslift", "scissor_lift": "sakselift",
    "telescopic_lift": "teleskoplift", "forklift": "gaffeltruck",
    "hand_truck": "håndtruck", "wheelbarrow": "trillebør",
    "concrete_mixer": "betonblander", "compressor": "kompressor",
    "generator": "generator", "welding_equipment": "svejseudstyr",
    "hammer_drill": "borehammer", "angle_grinder": "vinkelsliber",
    "trestle": "travis", "construction_hoist": "byggeelevator",
    "concrete_formwork": "betonform", "formwork": "forskalling",
    "tension_strap": "spændebånd", "crane_hook": "krankrog",
    "lifting_gear": "løftegrej", "ladder": "stige", "pallet": "palle",
    "storage_container": "opbevaringscontainer", "waste_container": "affaldscontainer",
    "dumpster": "skip", "water_tank": "vandbeholder", "diesel_tank": "dieseltank",
    # vehicles
    "car": "personbil", "van": "varevogn", "large_van": "stor varevogn",
    "pickup_truck": "pickup", "truck": "lastbil", "truck_with_crane": "lastbil med kran",
    "dump_truck": "tipvogn", "semi_trailer": "sættevogn", "tanker_truck": "tankvogn",
    "concrete_transport_truck": "betontransport", "dolly_trailer": "stiklevogn",
    "trailer": "trailer", "ambulance": "ambulance", "fire_truck": "brandvogn",
    "police_car": "politibil", "bus": "bus", "minibus": "minibus",
    "motorcycle": "motorcykel", "moped": "knallert", "bicycle": "cykel",
    "e_bike": "elcykel", "e_scooter": "elscooter", "industrial_truck": "truck",
    "pallet_jack": "palleløfter",
    # materials_on_site
    "rebar": "armering", "reinforcement_bars": "armeringsjern",
    "concrete_blocks": "betonblokke", "lightweight_concrete_blocks": "letklinkerblokke",
    "bricks": "mursten", "aerated_concrete": "porebeton",
    "concrete_elements": "betonelementer", "prefab_elements": "præfabelementer",
    "steel_beams": "stålbjælker", "steel_plates": "stålplader", "steel_pipes": "stålrør",
    "wood_planks": "træplanker", "plywood": "krydsfiner",
    "roofing_felt_rolls": "tagpapruller", "insulation_panels": "isoleringsplader",
    "mineral_wool": "rockwool", "gypsum_boards": "gipsplader",
    "windows_on_pallet": "vinduer på palle", "doors_on_pallet": "døre på palle",
    "plumbing_pipes": "vvs-rør", "cables": "kabler", "cable_conduit": "kabelrør",
    "sand": "sand", "gravel": "grus", "stone": "sten", "soil": "jord",
    "fill_sand": "fyldsand", "concrete_mix": "betonblanding", "mortar": "mørtel",
    "adhesive_bags": "limsække", "paint_buckets": "malingsspande",
    "waste_bags": "affaldssække", "pallets": "paller", "stacked_materials": "stablede materialer",
    # workers_and_activity
    "worker": "arbejder", "multiple_workers": "flere arbejdere",
    "group_of_workers": "gruppe arbejdere", "worker_active": "arbejder aktiv",
    "worker_break": "arbejder pause", "worker_climbing": "arbejder klatrer",
    "helmet": "hjelm", "orange_vest": "orange vest", "yellow_vest": "gul vest",
    "safety_equipment": "sikkerhedsudstyr", "safety_shoes": "sikkerhedssko",
    "safety_glasses": "sikkerhedsbriller", "hearing_protection": "høreværn",
    "welder": "svejser", "bricklayer": "murer", "carpenter": "tømrer",
    "electrician": "elektriker", "plumber": "vvs-mand", "crane_operator": "kranfører",
    "machine_operator": "maskinfører", "site_foreman": "arbejdsleder",
    "supervisor": "tilsynsførende", "no_activity": "ingen aktivitet",
    "active_construction_site": "aktiv byggeplads", "quiet_construction_site": "stille byggeplads",
    # weather
    "sunshine": "solskin", "partly_cloudy": "delvis skyet", "overcast": "overskyet",
    "gray_sky": "grå himmel", "fog": "tåge", "light_fog": "let tåge",
    "thick_fog": "tyk tåge", "haze": "dis", "rain": "regn", "light_rain": "let regn",
    "heavy_rain": "kraftig regn", "downpour": "styrtregn", "hail": "hagl",
    "snow": "sne", "light_snow": "let sne", "heavy_snowfall": "kraftigt snefald",
    "snow_on_ground": "sne på jord", "ice": "is", "frost": "frost",
    "hoarfrost": "rimfrost", "windy": "blæsende", "storm": "storm",
    "thunder": "torden", "rainbow": "regnbue", "cloud_cover": "skydække",
    "blue_sky": "blå himmel", "white_clouds": "hvide skyer", "clear_sky": "klar himmel",
    "low_cloud_cover": "lavt skydække", "high_sun": "høj sol", "low_sun": "lav sol",
    # light_and_time
    "daylight": "dagslys", "sunny_day": "solrig dag", "dark_day": "mørk dag",
    "dawn": "tusmørke morgen", "dusk": "tusmørke aften", "night": "nat",
    "artificial_lighting": "kunstig belysning", "work_light": "arbejdslys",
    "backlight": "modlys", "direct_sunlight": "direkte sollys",
    "diffuse_light": "diffust lys", "shadow": "skygge", "long_shadow": "lang skygge",
    "short_shadow": "kort skygge", "golden_light": "gyldent lys", "blue_light": "blåt lys",
    "clear_sunlight": "klart sollys", "sun_in_lens": "sol i linsen", "glare": "genskin",
    "lens_flare": "linserefleks", "distracting_glare": "irriterende genskin",
    "good_timelapse_lighting": "god timelapse-belysning",
    # safety_and_barriers
    "construction_site_fence": "byggepladshegn", "green_construction_fence": "byggepladshegn grønt",
    "construction_site_gate": "byggepladsport", "no_access_sign": "adgang forbudt skilt",
    "warning_sign": "advarselsskilt", "road_sign": "vejskilt", "safety_net": "sikkerhedsnet",
    "edge_protection": "kantbeskyttelse", "barrier": "afspærring", "warning_tape": "advarselsbånd",
    "traffic_cones": "kegler", "road_diversion": "vejomlægning", "fire_extinguisher": "brandslukker",
    "first_aid_cabinet": "førstehjælpsskab", "emergency_exit_sign": "nødudgangsskilt",
    # site_condition
    "tidy_site": "ryddig plads", "messy_site": "rodet plads", "very_messy": "meget rodet",
    "muddy_ground": "mudret underlag", "dry_ground": "tørt underlag",
    "wet_ground": "vådt underlag", "snow_covered": "snedækket", "ice_covered": "isdækket",
    "dusty": "støvende", "mud": "mudder", "puddles": "vandpytter",
    "flooding": "oversvømmelse", "erosion": "erosion",
    # surroundings
    "road": "vej", "sidewalk": "fortov", "asphalt": "asfalt", "pavement_tiles": "fliser",
    "grass": "græs", "garden": "have", "tree": "træ", "trees": "træer",
    "bush": "busk", "hedge": "hæk", "nature": "natur", "field": "mark",
    "forest": "skov", "lake": "sø", "stream": "å", "canal": "kanal", "harbor": "havn",
    "neighboring_building": "nabobygning", "neighbor_renovation": "nabo renovering",
    "parking": "parkering", "lamp_post": "lygtepæl", "electrical_cabinet": "elskab",
    "manhole_cover": "brønddæksel", "ditch": "grøft",
    # gdpr_safe
    "license_plate_visible": "nummerplade synlig", "person_visible": "person synlig",
    "face_visible": "ansigt synlig", "group_of_people": "gruppe mennesker",
    "pedestrian": "fodgænger", "cyclist": "cyklist",
    # anomalies_and_events
    "fire": "brand", "smoke": "røg", "flames": "ild", "fire_hazard": "brandfare",
    "water_damage": "vandskade", "flood_risk": "oversvømmelsesrisiko",
    "cloudburst": "skybrud", "structural_damage": "konstruktionsskade", "crack": "revne",
    "collapse_risk": "kollapsrisiko", "new_object": "nyt objekt",
    "missing_object": "manglende objekt", "unknown_object": "ukendt objekt",
    "abandoned_equipment": "efterladt udstyr", "theft_risk": "tyveririsiko",
    "vandalism": "hærværk", "unauthorized_person": "uvedkommende",
    "animal_on_site": "dyr på pladsen", "crane_alarm": "kranalarm",
    "accident": "ulykke", "safety_incident": "sikkerhedshændelse",
    # animals
    "dog": "hund", "cat": "kat", "bird": "fugl", "flock_of_birds": "flok fugle",
    "seagull": "måge", "rat": "rotte", "fox": "ræv", "hare": "hare",
    # camera_quality
    "clear_image": "klart billede", "foggy_image": "tåget billede",
    "dirty_lens": "beskidt linse", "condensation_on_lens": "kondens på linse",
    "obstruction_in_front_of_camera": "forhindring foran kamera",
    "overexposed": "overeksponeret", "underexposed": "undereksponeret",
    "correct_exposure": "korrekt eksponering", "motion_blur": "bevægelsesslør",
    "incorrect_focus": "forkert fokus", "night_image_ok": "natbillede ok",
    "night_image_too_dark": "natbillede for mørkt", "camera_moved": "kamera bevæget",
    "blown_highlights": "udbrændte højlys", "flare": "flare", "low_contrast": "lav kontrast",
    # change_detection
    "new_construction_since_last": "ny konstruktion siden sidst",
    "progress_since_last": "fremskridt siden sidst", "new_vehicle": "nyt køretøj",
    "new_machine": "ny maskine", "new_container": "ny container",
    "materials_removed": "materialer fjernet", "construction_removed": "konstruktion fjernet",
    "crane_position_changed": "kran position ændret", "new_floor_visible": "ny etage synlig",
    "roof_started": "tag påbegyndt", "facade_changed": "facade ændret",
    "no_change": "ingen ændring", "small_change": "lille ændring", "large_change": "stor ændring",
}

CANONICAL_TAG_OVERRIDES: dict[str, tuple[str, str]] = {
    "arbejder": ("worker", "Worker"),
    "arbejder_aktiv": ("worker_active", "Active worker"),
    "arbejdslys": ("work_light", "Work light"),
    "betonbil": ("concrete_truck", "Concrete truck"),
    "betonpumpe": ("concrete_pump", "Concrete pump"),
    "blå_himmel": ("blue_sky", "Blue sky"),
    "bygninger": ("buildings", "Buildings"),
    "byudsigt": ("city_view", "City view"),
    "dagslys": ("daylight", "Daylight"),
    "delvis_skyet": ("partly_cloudy", "Partly cloudy"),
    "direkte_sollys": ("direct_sunlight", "Direct sunlight"),
    "diffust_lys": ("diffuse_light", "Diffuse light"),
    "el_installation": ("electrical_installation", "Electrical installation"),
    "facade": ("facade", "Facade"),
    "facade_beklædning": ("facade_cladding", "Facade cladding"),
    "flare": ("lens_flare", "Lens flare"),
    "fundament": ("foundation", "Foundation"),
    "fundamentstøbning": ("foundation_pouring", "Foundation pouring"),
    "genskin": ("glare", "Glare"),
    "god_timelapse_belysning": ("good_timelapse_lighting", "Good timelapse lighting"),
    "grå_himmel": ("grey_sky", "Grey sky"),
    "gravemaskine": ("excavator", "Excavator"),
    "hagl": ("hail", "Hail"),
    "hvid_sky": ("white_cloud", "White cloud"),
    "hvide_skyer": ("white_clouds", "White clouds"),
    "høj_sol": ("high_sun", "High sun"),
    "irriterende_genskin": ("annoying_glare", "Annoying glare"),
    "klar_himmel": ("clear_sky", "Clear sky"),
    "klart_billede": ("clear_image", "Clear image"),
    "klart_sollys": ("clear_sunlight", "Clear sunlight"),
    "kondens_på_linse": ("lens_condensation", "Lens condensation"),
    "kraftig_regn": ("heavy_rain", "Heavy rain"),
    "lav_kontrast": ("low_contrast", "Low contrast"),
    "lav_sol": ("low_sun", "Low sun"),
    "let_regn": ("light_rain", "Light rain"),
    "linse_refleks": ("lens_reflection", "Lens reflection"),
    "modlys": ("backlight", "Backlight"),
    "mørk_dag": ("dark_day", "Dark day"),
    "natur": ("nature", "Nature"),
    "overeksponeret": ("overexposed", "Overexposed"),
    "overskyet": ("overcast", "Overcast"),
    "regn": ("rain", "Rain"),
    "skydække": ("cloud_cover", "Cloud cover"),
    "skygge": ("shadow", "Shadow"),
    "sol_i_linsen": ("sun_in_lens", "Sun in lens"),
    "solrig_dag": ("sunny_day", "Sunny day"),
    "solskin": ("sunshine", "Sunshine"),
    "tag": ("roof", "Roof"),
    "tagdækning": ("roofing", "Roofing"),
    "tagkonstruktion": ("roof_structure", "Roof structure"),
    "træ": ("tree", "Tree"),
    "træer": ("trees", "Trees"),
    "tåge": ("fog", "Fog"),
    "udbrændte_højlys": ("blown_highlights", "Blown highlights"),
    "undereksponeret": ("underexposed", "Underexposed"),
    "vvs_installation": ("plumbing_installation", "Plumbing installation"),
}


def _canonical_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    ascii_value = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_value = ascii_value.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_value)).strip("_")


def canonical_metadata(tag: str, da_hint: str = "") -> tuple[str, str, str]:
    """Returnér (canonical_tag, display_da, display_en) for et tag.

    Tags forventes at være ENGELSK (ny standard fra v3.x). Hvis tagget findes
    i CANONICAL_TAG_OVERRIDES er det et LEGACY dansk tag — bevares til
    bagudkompatibilitet med captures tagget før denne ændring.

    da_hint: AI-foreslået dansk oversættelse (fra new_tags_da ved et nyt,
             model-opfundet tag) — har højeste prioritet hvis angivet.
    """
    clean = tag.lower().strip().replace(" ", "_").replace("-", "_")

    if clean in CANONICAL_TAG_OVERRIDES:
        # Legacy dansk tag — korrelér til engelsk kanonisk for ensartet gruppering
        canonical, display_en = CANONICAL_TAG_OVERRIDES[clean]
        display_da = da_hint or PREDEFINED_DA_LABELS.get(canonical, clean.replace("_", " "))
        return canonical, display_da, display_en

    canonical = _canonical_slug(clean)
    display_en = clean.replace("_", " ").title()
    display_da = da_hint or PREDEFINED_DA_LABELS.get(canonical, "")
    if not display_da:
        # Ingen oversættelse kendt — markeres som 'pending' af kalderen, så
        # admin kan se i UI at det danske navn afventer udfyldelse/korrektion.
        display_da = display_en
    return canonical, display_da, display_en


def get_all_predefined() -> list[str]:
    """Returnér alle foruddefinerede tags som flad liste."""
    tags = []
    for cat_tags in PREDEFINED_TAGS.values():
        tags.extend(cat_tags)
    return sorted(set(tags))


def get_by_category(category: str) -> list[str]:
    return PREDEFINED_TAGS.get(category, [])


def get_categories() -> list[str]:
    return list(PREDEFINED_TAGS.keys())


# ── Database-integration ──────────────────────────────────────────────────────

VOCABULARY_DDL = """
CREATE TABLE IF NOT EXISTS ai_tag_vocabulary (
    id          SERIAL PRIMARY KEY,
    tag         TEXT UNIQUE NOT NULL,
    canonical_tag TEXT,
    display_name_da TEXT,
    display_name_en TEXT,
    translation_status TEXT DEFAULT 'pending',
    translation_source TEXT DEFAULT 'system',
    translation_updated_at TIMESTAMP WITH TIME ZONE,
    category    TEXT,
    count       INTEGER DEFAULT 1,
    first_seen  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    predefined  BOOLEAN DEFAULT FALSE,
    approved    BOOLEAN DEFAULT TRUE,
    rejected    BOOLEAN DEFAULT FALSE,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_vocab_tag ON ai_tag_vocabulary(tag);
CREATE INDEX IF NOT EXISTS idx_vocab_canonical_tag ON ai_tag_vocabulary(canonical_tag);
CREATE INDEX IF NOT EXISTS idx_vocab_approved ON ai_tag_vocabulary(approved, rejected);
"""


class TagVocabulary:
    """
    Dynamisk tag-vokabular der vokser med systemet.

    Bruges af OllamaService til at bygge prompts og gemme nye tags.
    """

    def __init__(self, db_session_factory):
        """
        db_session_factory: callable der returnerer en SQLAlchemy Session
        (samme factory som headend/main.py bruger)
        """
        self._get_db = db_session_factory
        self._ensure_table()
        self._seed_predefined()

    def _ensure_table(self):
        from sqlalchemy import text
        db_gen = self._get_db()
        db = next(db_gen)
        try:
            try:
                db.execute(text("SELECT 1 FROM ai_tag_vocabulary LIMIT 1")).fetchone()
                missing = self._missing_translation_columns(db)
                if missing:
                    try:
                        self._ensure_translation_columns(db)
                    except Exception as exc:
                        db.rollback()
                        still_missing = self._missing_translation_columns(db)
                        if still_missing:
                            log.warning("Vocabulary schema mangler kolonner %s og kunne ikke migreres: %s", still_missing, exc)
                        return
                db.commit()
                return
            except Exception:
                db.rollback()

            try:
                db.execute(text(VOCABULARY_DDL))
                self._ensure_translation_columns(db)
                db.commit()
            except Exception as e:
                log.warning("Vocabulary DDL: %s", e)
                db.rollback()
        finally:
            db_gen.close()

    def _missing_translation_columns(self, db) -> list[str]:
        from sqlalchemy import text
        required = {
            "canonical_tag",
            "display_name_da",
            "display_name_en",
            "translation_status",
            "translation_source",
            "translation_updated_at",
        }
        rows = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ai_tag_vocabulary'
        """)).fetchall()
        existing = {row[0] for row in rows}
        return sorted(required - existing)

    def _ensure_translation_columns(self, db):
        from sqlalchemy import text
        for ddl in (
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS canonical_tag TEXT",
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS display_name_da TEXT",
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS display_name_en TEXT",
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS translation_status TEXT DEFAULT 'pending'",
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS translation_source TEXT DEFAULT 'system'",
            "ALTER TABLE ai_tag_vocabulary ADD COLUMN IF NOT EXISTS translation_updated_at TIMESTAMP WITH TIME ZONE",
            "CREATE INDEX IF NOT EXISTS idx_vocab_canonical_tag ON ai_tag_vocabulary(canonical_tag)",
        ):
            db.execute(text(ddl))

    def _seed_predefined(self):
        """Indsæt foruddefinerede tags hvis tabellen er tom."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            result = db.execute(
                text("SELECT COUNT(*) FROM ai_tag_vocabulary WHERE predefined=TRUE")
            ).scalar()
            if result == 0:
                log.info("Seeding %d predefined tags...", len(get_all_predefined()))
                for category, tags in PREDEFINED_TAGS.items():
                    for tag in tags:
                        canonical, label_da, label_en = canonical_metadata(tag)
                        # Hvis vi har en kuraret dansk oversættelse (PREDEFINED_DA_LABELS),
                        # markeres den 'approved' — ellers 'pending' så admin kan se i UI
                        # at netop dette tag mangler korrekt dansk visningsnavn.
                        status = "approved" if canonical in PREDEFINED_DA_LABELS or tag in PREDEFINED_DA_LABELS else "pending"
                        db.execute(text("""
                            INSERT INTO ai_tag_vocabulary (
                                tag, canonical_tag, display_name_da, display_name_en,
                                translation_status, translation_source, translation_updated_at,
                                category, predefined, approved
                            )
                            VALUES (
                                :tag, :canonical, :label_da, :label_en,
                                :status, 'system', NOW(),
                                :cat, TRUE, TRUE
                            )
                            ON CONFLICT (tag) DO UPDATE SET
                                canonical_tag = COALESCE(ai_tag_vocabulary.canonical_tag, EXCLUDED.canonical_tag),
                                display_name_da = COALESCE(ai_tag_vocabulary.display_name_da, EXCLUDED.display_name_da),
                                display_name_en = COALESCE(ai_tag_vocabulary.display_name_en, EXCLUDED.display_name_en),
                                translation_status = COALESCE(ai_tag_vocabulary.translation_status, EXCLUDED.translation_status),
                                translation_source = COALESCE(ai_tag_vocabulary.translation_source, EXCLUDED.translation_source)
                        """), {"tag": tag, "canonical": canonical, "label_da": label_da, "label_en": label_en, "status": status, "cat": category})
                db.commit()
                log.info("Tag vocabulary seeded.")
        except Exception as e:
            log.error("Seed error: %s", e)
            db.rollback()
        finally:
            db.close()

    def get_approved_tags(self) -> list[str]:
        """Returnér alle godkendte tags (bruges i prompt)."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text(
                "SELECT COALESCE(canonical_tag, tag) FROM ai_tag_vocabulary WHERE approved=TRUE AND rejected=FALSE ORDER BY count DESC"
            )).fetchall()
            return [r[0] for r in rows]
        finally:
            db.close()

    def get_approved_by_category(self) -> dict[str, list[str]]:
        """Returnér godkendte tags grupperet på kategori."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text(
                "SELECT COALESCE(canonical_tag, tag), category FROM ai_tag_vocabulary WHERE approved=TRUE AND rejected=FALSE ORDER BY category, tag"
            )).fetchall()
            result: dict[str, list[str]] = {}
            for tag, cat in rows:
                cat = cat or "øvrige"
                result.setdefault(cat, []).append(tag)
            return result
        finally:
            db.close()

    def record_usage(
        self,
        tags: list[str],
        new_tags: list[str] | None = None,
        new_tags_da: dict[str, str] | None = None,
    ):
        """
        Registrér at tags blev brugt.
        new_tags: tags modellen opfandt selv (ENGELSK) — gemmes med approved=False til review.
        new_tags_da: AI-foreslået dansk oversættelse pr. nyt tag (fra Gemini/Ollama-svaret).
                     Hvis angivet, sættes translation_status='ai_suggested' i stedet for
                     'pending' — admin kan se i UI at det ER et forslag, ikke en fastlåst værdi,
                     og kan rette det hvis Gemini gættede helt skævt.
        """
        from sqlalchemy import text
        now = datetime.now(timezone.utc)
        new_tags_da = new_tags_da or {}
        db = next(self._get_db())
        try:
            for tag in tags:
                db.execute(text("""
                    UPDATE ai_tag_vocabulary
                    SET count = count + 1, last_seen = :now
                    WHERE tag = :tag
                """), {"tag": tag, "now": now})

            if new_tags:
                for tag in new_tags:
                    tag_clean = tag.lower().strip().replace(" ", "_").replace("-", "_")
                    if len(tag_clean) < 3 or len(tag_clean) > 60:
                        continue
                    da_hint = new_tags_da.get(tag) or new_tags_da.get(tag_clean) or ""
                    canonical, label_da, label_en = canonical_metadata(tag_clean, da_hint=da_hint)
                    status = "ai_suggested" if da_hint else "pending"
                    db.execute(text("""
                        INSERT INTO ai_tag_vocabulary (
                            tag, canonical_tag, display_name_da, display_name_en,
                            translation_status, translation_source, translation_updated_at,
                            category, predefined, approved, first_seen, last_seen
                        )
                        VALUES (
                            :tag, :canonical, :label_da, :label_en,
                            :status, 'gemini', :now,
                            'model_invented', FALSE, FALSE, :now, :now
                        )
                        ON CONFLICT (tag) DO UPDATE SET
                            count = ai_tag_vocabulary.count + 1,
                            last_seen = :now,
                            canonical_tag = COALESCE(ai_tag_vocabulary.canonical_tag, EXCLUDED.canonical_tag),
                            display_name_da = COALESCE(ai_tag_vocabulary.display_name_da, EXCLUDED.display_name_da),
                            display_name_en = COALESCE(ai_tag_vocabulary.display_name_en, EXCLUDED.display_name_en)
                    """), {"tag": tag_clean, "canonical": canonical, "label_da": label_da, "label_en": label_en, "status": status, "now": now})
                log.info("Stored %d new model-invented tags for review (%d med dansk forslag)",
                         len(new_tags), sum(1 for t in new_tags if new_tags_da.get(t)))

            db.commit()
        except Exception as e:
            log.error("record_usage error: %s", e)
            db.rollback()
        finally:
            db.close()

    def get_pending_review(self) -> list[dict]:
        """Tags opfundet af modellen der afventer godkendelse.
        Inkluderer canonical_tag + dansk/engelsk visningsnavn + translation_status,
        så Tag Review-UI kan vise og lade admin rette AI's oversættelsesforslag.
        """
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text("""
                SELECT id, tag, canonical_tag, display_name_da, display_name_en,
                       translation_status, count, first_seen, last_seen
                FROM ai_tag_vocabulary
                WHERE approved=FALSE AND rejected=FALSE
                ORDER BY count DESC, first_seen ASC
            """)).fetchall()
            return [{
                "id": r[0], "tag": r[1], "canonical_tag": r[2],
                "display_name_da": r[3], "display_name_en": r[4],
                "translation_status": r[5], "count": r[6],
                "first_seen": str(r[7]), "last_seen": str(r[8]),
            } for r in rows]
        finally:
            db.close()

    def update_translation(self, tag_id: int, display_name_da: str | None = None,
                            display_name_en: str | None = None) -> None:
        """Admin retter et AI-foreslået (eller manglende) dansk/engelsk visningsnavn.
        Sætter translation_status='approved' — markerer at en menneske har bekræftet det.
        """
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text("""
                UPDATE ai_tag_vocabulary
                SET display_name_da = COALESCE(:da, display_name_da),
                    display_name_en = COALESCE(:en, display_name_en),
                    translation_status = 'approved',
                    translation_source = 'human',
                    translation_updated_at = NOW()
                WHERE id = :id
            """), {"id": tag_id, "da": display_name_da, "en": display_name_en})
            db.commit()
        finally:
            db.close()

    def approve(self, tag_id: int, category: str | None = None):
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text(
                "UPDATE ai_tag_vocabulary SET approved=TRUE, rejected=FALSE, category=COALESCE(:cat, category) WHERE id=:id"
            ), {"id": tag_id, "cat": category})
            db.commit()
        finally:
            db.close()

    def reject(self, tag_id: int):
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text(
                "UPDATE ai_tag_vocabulary SET rejected=TRUE, approved=FALSE WHERE id=:id"
            ), {"id": tag_id})
            db.commit()
        finally:
            db.close()
