# -*- coding: utf-8 -*-
"""The fourteen frames of the reel.

Every string here is copied from the campus-drive poster. Nothing about
salary, selection rounds, job titles, hostel/transport facilities,
internship stipends or documents appears on that poster, so none of it
appears here either.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

import icons
from brandkit import (CRIMSON, DEVA_BOLD, DEVA_REG, GOLD, GOLD_LIGHT, H, ICE,
                      LAT_BOLD, NAVY_DEEP, STEEL, W, WHITE, base, card,
                      chevron, diagonal_ribbon, finish, fit, footer, header,
                      measure, paragraph, rule, text, tracked, wrap)

DRIVE = "कॅम्पस ड्राईव्ह"
COLLEGE = "मातोश्री अभियांत्रिकी व संशोधन केंद्र"
PLACE = "एकलहरे, नाशिक"


def _badge(img: Image.Image, y: int, label: str, fill=GOLD, ink=NAVY_DEEP) -> None:
    """A small pill label, centred."""
    size = 34
    width = fit(label, DEVA_BOLD, size, 700)
    text_w = measure(label, DEVA_BOLD, width)[0]
    pad_x, pad_y = 34, 16
    box = (W // 2 - text_w // 2 - pad_x, y, W // 2 + text_w // 2 + pad_x,
           y + width + pad_y * 2)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=(box[3] - box[1]) // 2,
                                            fill=tuple(fill) + (255,))
    img.alpha_composite(layer)
    text(img, (W // 2, y + pad_y - 2), label, DEVA_BOLD, width, fill=ink, anchor="ma")


def _tick(img: Image.Image, center: tuple[int, int], size: int = 54) -> None:
    icons.paste(img, icons.check(size, GOLD + (255,)), center)
    icons.paste(img, icons.check_mark(size, NAVY_DEEP + (255,)), center)


# --------------------------------------------------------------------------


def s01_hook(path: str) -> str:
    img = base("navy")
    diagonal_ribbon(img, 450, 200, GOLD, 255, slant=30)
    header(img, DRIVE)
    tracked(img, (W // 2, 330), "अभियांत्रिकी विद्यार्थ्यांसाठी", DEVA_BOLD, 40,
            ICE, tracking=3, center=True)
    text(img, (W // 2, 470), "मोठी संधी!", DEVA_BOLD, 118, fill=NAVY_DEEP,
         anchor="ma")
    rule(img, W // 2, 740, 200, 10, GOLD, center=True)
    paragraph(img, (W // 2, 810), "उद्योग विश्वाशी थेट जोडणारी संधी!",
              DEVA_BOLD, 62, W - 200, fill=WHITE)
    paragraph(img, (W // 2, 990),
              "आपल्या करिअरची मजबूत सुरुवात उद्योगांसोबत!",
              DEVA_REG, 44, W - 240, fill=ICE)
    for i, x in enumerate((W // 2 - 90, W // 2, W // 2 + 90)):
        chevron(img, x, 1240, 34, GOLD, 12, alpha=90 + i * 70)
    text(img, (W // 2, 1360), "कुशल युवा  ·  समृद्ध भारत", DEVA_BOLD, 44,
         fill=GOLD_LIGHT, anchor="ma")
    footer(img)
    return finish(img, path)


def s02_drive(path: str) -> str:
    img = base("deep")
    header(img, DRIVE)
    _badge(img, 380, "योग्य मनुष्यबळ  ·  उज्ज्वल भविष्य")
    text(img, (W // 2, 560), DRIVE, DEVA_BOLD, 118, fill=WHITE, anchor="ma",
         glow=GOLD)
    rule(img, W // 2, 760, 320, 10, GOLD, center=True)
    paragraph(img, (W // 2, 850),
              "ईगलहाय-टेक इंडस्ट्रियल कॉर्पोरेट प्रा. लि. आणि मातोश्री अभियांत्रिकी व "
              "संशोधन केंद्र, एकलहरे, नाशिक यांच्या सहकार्याने आयोजित",
              DEVA_REG, 44, W - 200, fill=ICE)
    icons.paste(img, icons.spark(90, GOLD + (255,)), (W // 2, 1300))
    footer(img)
    return finish(img, path)


def s03_company(path: str) -> str:
    img = base("navy")
    header(img, DRIVE)
    tracked(img, (W // 2, 360), "आयोजक", DEVA_BOLD, 40, GOLD, tracking=10,
            center=True)
    text(img, (W // 2, 470), "Eagle Hi-tech", LAT_BOLD, 104, fill=WHITE,
         anchor="ma", shadow=10)
    text(img, (W // 2, 610), "Industrial Corporate Pvt. Ltd.", LAT_BOLD, 46,
         fill=GOLD_LIGHT, anchor="ma")
    rule(img, W // 2, 710, 240, 8, GOLD, center=True)
    paragraph(img, (W // 2, 780),
              "ईगलहाय-टेक इंडस्ट्रियल कॉर्पोरेट प्रा. लि.", DEVA_BOLD, 52,
              W - 200, fill=WHITE)
    tracked(img, (W // 2, 940), "PRECISION  ·  PERFORMANCE  ·  PERFECTION",
            LAT_BOLD, 30, STEEL, tracking=4, center=True)
    paragraph(img, (W // 2, 1080),
              "उद्योगाचा विकास, तरुणांचे उज्ज्वल भविष्य!", DEVA_BOLD, 46,
              W - 220, fill=GOLD)
    paragraph(img, (W // 2, 1210),
              "तुमचा टॅलेंट पार्टनर.  तुमचा ग्रोथ पार्टनर.", DEVA_REG, 40,
              W - 220, fill=ICE)
    footer(img)
    return finish(img, path)


def s04_college(path: str) -> str:
    img = base("deep")
    header(img, DRIVE)
    tracked(img, (W // 2, 340), "सहकार्याने", DEVA_BOLD, 40, GOLD, tracking=10,
            center=True)
    icons.paste(img, icons.building(150, WHITE + (255,)), (W // 2, 520))
    paragraph(img, (W // 2, 650), COLLEGE, DEVA_BOLD, 62, W - 160, fill=WHITE)
    text(img, (W // 2, 880), PLACE, DEVA_BOLD, 56, fill=GOLD, anchor="ma")
    rule(img, W // 2, 990, 220, 8, GOLD, center=True)
    text(img, (W // 2, 1060), "|| ज्ञान आज, उज्ज्वल उद्या ||", DEVA_REG, 44,
         fill=ICE, anchor="ma")
    paragraph(img, (W // 2, 1200), "अन स्वच्छ महाविद्यालय", DEVA_REG, 38,
              W - 240, fill=STEEL)
    footer(img)
    return finish(img, path)


def s05_date(path: str) -> str:
    img = base("gold")
    header(img, DRIVE, on_gold=True)
    icons.paste(img, icons.calendar(130, NAVY_DEEP + (255,)), (W // 2, 400))
    tracked(img, (W // 2, 520), "दिनांक", DEVA_BOLD, 42, NAVY_DEEP, tracking=10,
            center=True)
    text(img, (W // 2, 620), "8 – 9", LAT_BOLD, 200, fill=NAVY_DEEP, anchor="ma")
    text(img, (W // 2, 880), "सप्टेंबर 2026", DEVA_BOLD, 92, fill=NAVY_DEEP,
         anchor="ma")
    rule(img, W // 2, 1040, 200, 10, NAVY_DEEP, center=True)
    text(img, (W // 2, 1110), "(2 दिवस)", DEVA_BOLD, 56, fill=CRIMSON, anchor="ma")
    paragraph(img, (W // 2, 1260), "तारीख लक्षात ठेवा — तयारीला आजपासून सुरुवात करा!",
              DEVA_REG, 40, W - 200, fill=(90, 60, 10))
    footer(img, on_gold=True)
    return finish(img, path)


def s06_venue(path: str) -> str:
    img = base("navy")
    header(img, DRIVE)
    icons.paste(img, icons.pin(140, GOLD + (255,)), (W // 2, 430))
    tracked(img, (W // 2, 550), "स्थळ", DEVA_BOLD, 42, GOLD, tracking=10,
            center=True)
    paragraph(img, (W // 2, 660), COLLEGE, DEVA_BOLD, 64, W - 160, fill=WHITE)
    text(img, (W // 2, 900), PLACE, DEVA_BOLD, 60, fill=GOLD_LIGHT, anchor="ma")
    card(img, (120, 1080, W - 120, 1300), fill=(255, 255, 255, 18))
    paragraph(img, (W // 2, 1130),
              "याच कॅम्पसवर उद्योग विश्वाशी थेट भेट", DEVA_REG, 42, W - 220,
              fill=ICE)
    footer(img)
    return finish(img, path)


def s07_eligible(path: str) -> str:
    img = base("deep")
    header(img, DRIVE)
    icons.paste(img, icons.people(150, GOLD + (255,)), (W // 2, 430))
    tracked(img, (W // 2, 560), "पात्र विद्यार्थी", DEVA_BOLD, 42, GOLD,
            tracking=8, center=True)
    paragraph(img, (W // 2, 680), "अभियांत्रिकीचे विद्यार्थी", DEVA_BOLD, 76,
              W - 160, fill=WHITE)
    _badge(img, 850, "सर्व शाखा")
    paragraph(img, (W // 2, 1030),
              "गुणवत्तापूर्ण व कुशल तरुणांना विविध औद्योगिक संधी उपलब्ध करून "
              "देण्यासाठी आम्ही आपल्यासोबत आहोत.", DEVA_REG, 42, W - 200,
              fill=ICE)
    footer(img)
    return finish(img, path)


def s08_pillars(path: str) -> str:
    img = base("navy")
    header(img, DRIVE)
    paragraph(img, (W // 2, 300), "उद्योगांसोबत करिअरची नवी उंची गाठा!",
              DEVA_BOLD, 62, W - 160, fill=WHITE)
    rule(img, W // 2, 500, 200, 8, GOLD, center=True)
    rows = [(icons.factory, "वास्तविक उद्योग अनुभव"),
            (icons.growth, "स्थिर करिअर विकास"),
            (icons.handshake, "विश्वसनीय संस्थेसोबत काम करण्याची संधी")]
    size = min(fit(label, DEVA_BOLD, 46, 560) for _, label in rows)
    y = 620
    for glyph, label in rows:
        card(img, (110, y, W - 110, y + 240), fill=(255, 255, 255, 16))
        icons.paste(img, glyph(96, GOLD + (255,)), (240, y + 120))
        lines = wrap(label, DEVA_BOLD, size, 580)
        ty = y + 120 - (len(lines) * int(size * 1.35)) // 2
        for line in lines:
            text(img, (350, ty), line, DEVA_BOLD, size, fill=WHITE, anchor="la")
            ty += int(size * 1.35)
        y += 290
    footer(img)
    return finish(img, path)


def _reasons(path: str, items: list[str], first: bool) -> str:
    img = base("deep")
    header(img, DRIVE)
    if first:
        diagonal_ribbon(img, 300, 130, CRIMSON, 255, slant=40)
        paragraph(img, (W // 2, 322), "सामील होण्याची कारणे!", DEVA_BOLD, 58,
                  W - 200, fill=WHITE)
    else:
        tracked(img, (W // 2, 330), "आणखी कारणे", DEVA_BOLD, 40, GOLD,
                tracking=8, center=True)
    y = 560 if first else 600
    for item in items:
        _tick(img, (150, y + 46))
        size = fit(item, DEVA_BOLD, 46, 740)
        lines = wrap(item, DEVA_BOLD, size, 740)
        ty = y + 46 - (len(lines) * int(size * 1.35)) // 2
        for line in lines:
            text(img, (215, ty), line, DEVA_BOLD, size, fill=WHITE, anchor="la")
            ty += int(size * 1.35)
        y += 230
    footer(img)
    return finish(img, path)


def s09_reasons_a(path: str) -> str:
    return _reasons(path, [
        "प्रतिष्ठित औद्योगिक संस्थांसोबत काम करण्याची संधी",
        "कौशल्य विकास आणि प्रत्यक्ष अनुभव",
        "विकासाभिमुख आणि प्रेरणादायी कार्यपरिसर",
    ], first=True)


def s10_reasons_b(path: str) -> str:
    return _reasons(path, [
        "PF, ESIC इत्यादी कायदेशीर सुविधा",
        "5000+ सक्रिय व्यावसायिकांचा भाग बनण्याची संधी",
    ], first=False)


def s11_services(path: str) -> str:
    img = base("navy")
    header(img, DRIVE)
    tracked(img, (W // 2, 300), "आमच्या प्रमुख सेवा", DEVA_BOLD, 46, GOLD,
            tracking=6, center=True)
    rule(img, W // 2, 400, 180, 8, GOLD, center=True)
    grid = [(icons.people, "औद्योगिक\nमनुष्यबळ पुरवठा"),
            (icons.building, "सुविधा\nव्यवस्थापन"),
            (icons.tools, "फॅब्रिकेशन आणि\nअसेंब्ली"),
            (icons.shield, "सिक्युरिटी\nसेवा"),
            (icons.broom, "हाउसकीपिंग\nसेवा"),
            (icons.growth, "टॅलेंट सोल्युशन्स\nॲडव्हायझरी")]
    cell_w, cell_h = 400, 330
    left, top = W // 2 - cell_w - 20, 490
    for index, (glyph, label) in enumerate(grid):
        col, row = index % 2, index // 2
        x = left + col * (cell_w + 40)
        y = top + row * (cell_h + 30)
        card(img, (x, y, x + cell_w, y + cell_h), fill=(255, 255, 255, 15))
        icons.paste(img, glyph(90, GOLD + (255,)), (x + cell_w // 2, y + 92))
        ty = y + 168
        for line in label.split("\n"):
            size = fit(line, DEVA_BOLD, 38, cell_w - 50)
            text(img, (x + cell_w // 2, ty), line, DEVA_BOLD, size, fill=WHITE,
                 anchor="ma")
            ty += 54
    footer(img)
    return finish(img, path)


def s12_scale(path: str) -> str:
    img = base("deep")
    header(img, DRIVE)
    text(img, (W // 2, 470), "5000+", LAT_BOLD, 210, fill=GOLD, anchor="ma",
         glow=GOLD)
    paragraph(img, (W // 2, 760), "सक्रिय व्यावसायिकांचा भाग बनण्याची संधी",
              DEVA_BOLD, 56, W - 160, fill=WHITE)
    rule(img, W // 2, 980, 220, 8, GOLD, center=True)
    paragraph(img, (W // 2, 1060), "तुमचा टॅलेंट पार्टनर.  तुमचा ग्रोथ पार्टनर.",
              DEVA_REG, 44, W - 200, fill=ICE)
    footer(img)
    return finish(img, path)


def s13_contact(path: str) -> str:
    img = base("navy")
    header(img, DRIVE)
    tracked(img, (W // 2, 300), "संपर्क साधा", DEVA_BOLD, 46, GOLD, tracking=8,
            center=True)
    rule(img, W // 2, 400, 180, 8, GOLD, center=True)
    rows = [(icons.phone, "+91 8830087156", LAT_BOLD, 54),
            (icons.phone, "+91 9623200898", LAT_BOLD, 54),
            (icons.mail, "hr@eaglehitec.com", LAT_BOLD, 44),
            (icons.mail, "info@eaglehitec.com", LAT_BOLD, 44),
            (icons.globe, "www.eaglehitec.com", LAT_BOLD, 44)]
    y = 520
    for glyph, label, face, size in rows:
        icons.paste(img, glyph(64, GOLD + (255,)), (170, y + 34))
        text(img, (250, y + 34 - size // 2 - 4), label, face, size, fill=WHITE,
             anchor="la")
        y += 132
    card(img, (110, 1230, W - 110, 1420), fill=(255, 255, 255, 16))
    text(img, (W // 2, 1276), "सुरेश औटे", DEVA_BOLD, 56, fill=GOLD, anchor="ma")
    text(img, (W // 2, 1350), "संचालक", DEVA_REG, 40, fill=ICE, anchor="ma")
    footer(img)
    return finish(img, path)


def s14_cta(path: str) -> str:
    img = base("navy")
    diagonal_ribbon(img, 1330, 150, GOLD, 255, slant=70)
    header(img, DRIVE)
    paragraph(img, (W // 2, 330), "संधी आजची, उत्कर्ष उद्याचा!", DEVA_BOLD, 66,
              W - 160, fill=GOLD)
    paragraph(img, (W // 2, 470), "चला, उद्योगांना नवी उंची देऊया!", DEVA_BOLD,
              58, W - 160, fill=WHITE)
    rule(img, W // 2, 620, 240, 8, GOLD, center=True)
    text(img, (W // 2, 700), "Eagle Hi-tech", LAT_BOLD, 88, fill=WHITE,
         anchor="ma", shadow=8)
    text(img, (W // 2, 815), "Industrial Corporate Pvt. Ltd.", LAT_BOLD, 40,
         fill=GOLD_LIGHT, anchor="ma")
    text(img, (W // 2, 920), DRIVE, DEVA_BOLD, 62, fill=WHITE, anchor="ma")
    paragraph(img, (W // 2, 1030), f"{COLLEGE}, {PLACE}", DEVA_REG, 40,
              W - 200, fill=ICE)
    text(img, (W // 2, 1352), "8 – 9 सप्टेंबर 2026", DEVA_BOLD, 66,
         fill=NAVY_DEEP, anchor="ma")
    text(img, (W // 2, 1560), "+91 8830087156  ·  +91 9623200898", LAT_BOLD, 44,
         fill=WHITE, anchor="ma")
    text(img, (W // 2, 1640), "www.eaglehitec.com", LAT_BOLD, 40, fill=GOLD,
         anchor="ma")
    footer(img, note="माणसं  ·  उद्योग  ·  प्रगती  ·  एकत्र")
    return finish(img, path)


SCENES = [s01_hook, s02_drive, s03_company, s04_college, s05_date, s06_venue,
          s07_eligible, s08_pillars, s09_reasons_a, s10_reasons_b, s11_services,
          s12_scale, s13_contact, s14_cta]


def build_all(outdir: str) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for index, scene in enumerate(SCENES, start=1):
        paths.append(scene(os.path.join(outdir, f"{index:02d}-{scene.__name__[4:]}.png")))
    return paths
