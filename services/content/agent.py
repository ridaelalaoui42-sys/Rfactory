"""
AI Content & Metadata Generation Agent for Animal & Celebrity Face Puzzle Reels Factory.
Generates puzzle configurations, titles, captions, short engagement questions,
and relevant hashtags in multiple languages (en, fr, ar, es) with zero paid API keys required.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from services.assets.generator import ANIMAL_CATALOG


@dataclass
class GeneratedPuzzleIdea:
    idea_id: str
    species: str
    display_name: str
    template_id: str
    title: str
    hook_question: str
    caption: str
    hashtags: str
    language: str
    seed: int
    background_hex: str
    object_count: int
    offset_distance_px: int
    cycles: int
    hold_ratio: float
    slice_x_ratio: Tuple[float, float]


LANGUAGE_TEMPLATES: Dict[str, Dict[str, object]] = {
    "en": {
        "hooks_outline": [
            "Can you pause the video at the exact millisecond the {animal} and all {count} eggs lock into the blue outline?",
            "99% of people miss the exact frame! Can you stop the {animal} inside the blue silhouette on your first try?",
            "Focus your eyes: pause right when the {animal} and every speckled egg align perfectly!",
        ],
        "hooks_missing": [
            "Can you stop the moving piece at the exact moment the {animal} is 100% restored?",
            "Harder than it looks! Pause the video when the sliding fragment completes the {animal} with zero gap!",
            "Test your reflexes: take a screenshot the instant the missing yellow section of the {animal} locks into place!",
        ],
        "hooks_face_slide": [
            "Can you lock the sliding eyes & nose band onto the {animal} portrait on your very first pause?",
            "98% of players miss by a pixel! Pause right when the {animal}'s facial features snap into place!",
            "Celebrity Face Challenge: stop the moving eye slice so the {animal} looks 100% complete!",
        ],
        "hooks_face_3band": [
            "All 3 face bands are moving in opposite directions! Can you freeze the {animal} portrait in exact alignment?",
            "Triple-Band Face Puzzle: pause at the exact millisecond the forehead, eyes, and smile of the {animal} lock together!",
            "Only sharp eyes can align this 3-way split of the {animal} on try #1!",
        ],
        "cta": [
            "Drop a 🎯 in the comments if you nailed it on the first try!",
            "Screenshot your best pause and tell us how many tries it took! 👇",
            "Did you catch it on try #1 or #2? Comment below!",
        ],
        "hashtags": "#PuzzleReels #PauseChallenge #CelebrityPuzzle #FacePuzzle #AnimalPuzzle #BrainTeaser #ReelsChallenge",
    },
    "fr": {
        "hooks_outline": [
            "Pouvez-vous mettre en pause au moment exact où le {animal} et les {count} œufs s'alignent dans le contour bleu ?",
        ],
        "hooks_missing": [
            "Arrêtez la pièce mobile à la milliseconde exacte où le {animal} est complètement reconstitué !",
        ],
        "hooks_face_slide": [
            "Défi Visage Célèbre : mettez en pause quand le regard du {animal} s'aligne parfaitement !",
        ],
        "hooks_face_3band": [
            "Les 3 bandes du visage bougent en sens inverse ! Pouvez-vous aligner le portrait du {animal} du premier coup ?",
        ],
        "cta": [
            "Dites-nous en commentaire combien d'essais il vous a fallu ! 🎯",
        ],
        "hashtags": "#DefiPause #PuzzleVisuel #VisageCelebre #JeuDeReflexe #ReelsFR",
    },
    "ar": {
        "hooks_outline": [
            "هل يمكنك إيقاف الفيديو في اللحظة الدقيقة التي يتطابق فيها {animal} مع الإطار الأزرق؟",
        ],
        "hooks_missing": [
            "تحدي التركيز: أوقف الصورة عندما تكتمل القطعة المفقودة من {animal} تماماً!",
        ],
        "hooks_face_slide": [
            "تحدي وجوه المشاهير: أوقف الشريط المتحرك عندما تتطابق ملامح {animal} بنسبة 100%!",
        ],
        "hooks_face_3band": [
            "تحدي الأشرطة الثلاثة: هل يمكنك تجميد وجه {animal} في لحظة التطابق التام؟",
        ],
        "cta": [
            "شاركنا في التعليقات كم محاولة احتجت! 🎯",
        ],
        "hashtags": "#تحدي_التركيز #ألغاز_بصرية #تحدي_المشاهير #تحدي_إيقاف_الصورة #ريلز",
    },
}

PALETTE_VARIANTS = ["#F2FAFF", "#F3F8FF", "#EFFAF6", "#FFF9F2", "#F4F6FF", "#F0FBFF"]

VALID_TEMPLATES = ("OUTLINE_MATCH", "MISSING_PIECE_SLIDE", "FACE_FEATURE_SLIDE", "FACE_SPLIT_3BAND")


class ContentGenerationAgent:
    def generate_idea(
        self,
        species: Optional[str] = None,
        template_id: Optional[str] = None,
        language: str = "en",
        seed: int = 1001,
    ) -> GeneratedPuzzleIdea:
        rng = random.Random(seed)
        lang_pack = LANGUAGE_TEMPLATES.get(language, LANGUAGE_TEMPLATES["en"])

        if species:
            spec_entry = next((s for s in ANIMAL_CATALOG if s["species"] == species), ANIMAL_CATALOG[0])
        else:
            spec_entry = ANIMAL_CATALOG[seed % len(ANIMAL_CATALOG)]

        chosen_species = str(spec_entry["species"])
        display_name = str(spec_entry["display_name"])
        chosen_template = template_id or str(spec_entry["template_affinity"])
        if chosen_template not in VALID_TEMPLATES:
            chosen_template = "OUTLINE_MATCH"

        obj_count = 5 if seed == 1001 else rng.choice([4, 5, 5])
        offset_px = 165 if seed == 1001 else rng.choice([150, 165, 175])
        cycles = 5
        hold_ratio = 0.14
        bg_hex = str(spec_entry.get("default_bg") or PALETTE_VARIANTS[seed % len(PALETTE_VARIANTS)])
        slice_x = (0.27, 0.51) if chosen_species != "giraffe" else (0.29, 0.53)

        if chosen_template == "OUTLINE_MATCH":
            hooks = list(lang_pack["hooks_outline"])  # type: ignore
            hook = rng.choice(hooks).format(animal=display_name, count=obj_count)
            title = f"{display_name} Outline Lock Challenge (#{seed})"
        elif chosen_template == "FACE_FEATURE_SLIDE":
            hooks = list(lang_pack.get("hooks_face_slide", lang_pack["hooks_missing"]))  # type: ignore
            hook = rng.choice(hooks).format(animal=display_name, count=obj_count)
            title = f"{display_name} Face Feature Slide Challenge (#{seed})"
        elif chosen_template == "FACE_SPLIT_3BAND":
            hooks = list(lang_pack.get("hooks_face_3band", lang_pack["hooks_missing"]))  # type: ignore
            hook = rng.choice(hooks).format(animal=display_name, count=obj_count)
            title = f"{display_name} 3-Band Face Split Puzzle (#{seed})"
        else:
            hooks = list(lang_pack["hooks_missing"])  # type: ignore
            hook = rng.choice(hooks).format(animal=display_name, count=obj_count)
            title = f"{display_name} Missing Piece Slide Puzzle (#{seed})"

        ctas = list(lang_pack["cta"])  # type: ignore
        cta = rng.choice(ctas)
        hashtags = str(lang_pack["hashtags"])
        caption = f"{hook}\n\n{cta}\n\n{hashtags}"

        idea_hash = hashlib.sha256(f"{chosen_species}:{chosen_template}:{seed}:{language}".encode()).hexdigest()[:12]
        return GeneratedPuzzleIdea(
            idea_id=f"idea_{idea_hash}",
            species=chosen_species,
            display_name=display_name,
            template_id=chosen_template,
            title=title,
            hook_question=hook,
            caption=caption,
            hashtags=hashtags,
            language=language,
            seed=seed,
            background_hex=bg_hex,
            object_count=obj_count,
            offset_distance_px=offset_px,
            cycles=cycles,
            hold_ratio=hold_ratio,
            slice_x_ratio=slice_x,
        )

    def generate_batch_ideas(
        self,
        count: int = 10,
        template_filter: str = "ALL",
        language: str = "en",
        base_seed: int = 1001,
    ) -> List[GeneratedPuzzleIdea]:
        ideas: List[GeneratedPuzzleIdea] = []
        for idx in range(count):
            spec = ANIMAL_CATALOG[idx % len(ANIMAL_CATALOG)]
            species = str(spec["species"])
            if template_filter in VALID_TEMPLATES:
                tmpl = template_filter
            else:
                tmpl = str(spec["template_affinity"])
            seed = (1001 + idx) if base_seed == 1001 else (base_seed + idx * 17)
            ideas.append(
                self.generate_idea(
                    species=species,
                    template_id=tmpl,
                    language=language,
                    seed=seed,
                )
            )
        return ideas
