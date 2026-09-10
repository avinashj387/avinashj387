# -*- coding: utf-8 -*-
"""Marathi voice-over: the script, and two ways to speak it.

Every line restates something printed on the campus-drive poster. Numbers are
spelled out the way a Marathi announcer would read them, so a TTS engine does
not fall back to English digits.

    python3 voiceover.py --engine edge     # neural male voice (needs network)
    python3 voiceover.py --engine espeak   # offline fallback, robotic
"""

SCRIPT = [
    ("01-hook",
     "अभियांत्रिकी विद्यार्थ्यांनो, तुमच्यासाठी मोठी संधी!"),
    ("02-drive",
     "ईगलहाय-टेक तर्फे कॅम्पस ड्राईव्ह!"),
    ("03-company",
     "उद्योगाचा विकास, तरुणांचे उज्ज्वल भविष्य."),
    ("04-college",
     "मातोश्री अभियांत्रिकी व संशोधन केंद्र, एकलहरे, नाशिक येथे."),
    ("05-date",
     "आठ आणि नऊ सप्टेंबर दोन हजार सव्वीस. दोन दिवस."),
    ("06-venue",
     "स्थळ — मातोश्री कॅम्पस, एकलहरे, नाशिक."),
    ("07-eligible",
     "अभियांत्रिकीच्या सर्व शाखांचे विद्यार्थी पात्र आहेत."),
    ("08-pillars",
     "वास्तविक उद्योग अनुभव, स्थिर करिअर विकास, विश्वसनीय संस्थेसोबत संधी."),
    ("09-reasons_a",
     "प्रतिष्ठित संस्थांसोबत काम, कौशल्य विकास आणि प्रत्यक्ष अनुभव."),
    ("10-reasons_b",
     "पी एफ, ई एस आय सी कायदेशीर सुविधा."),
    ("11-services",
     "मनुष्यबळ पुरवठा, सुविधा व्यवस्थापन, फॅब्रिकेशन, सिक्युरिटी, "
     "हाउसकीपिंग आणि टॅलेंट सोल्युशन्स."),
    ("12-scale",
     "पाच हजारांहून अधिक व्यावसायिकांचा भाग बना."),
    ("13-contact",
     "संपर्क — आठ आठ तीन शून्य शून्य आठ सात एक पाच सहा."),
    ("14-cta",
     "संधी आजची, उत्कर्ष उद्याचा! आजच तयार व्हा!"),
]

# The neural voice to prefer: a male Marathi (mr-IN) speaker.
EDGE_VOICE = "mr-IN-ManoharNeural"
EDGE_RATE = "+8%"
