# ruff: noqa: E501 - translated wording reads better on one line
"""Plain-language wording in English, Telugu and Hindi. Wording only: every value shown to a customer comes
from a tool, a document or the database. The Telugu and Hindi text was written for this prototype and
hasn't been reviewed by a medical or insurance translator."""

from __future__ import annotations

# (status → meaning, what to do next)
CLAIM_STATUS: dict[str, dict[str, tuple[str, str, str]]] = {
    "RECEIVED": {
        "en": ("Received", "We have your claim, and nobody has started reviewing it yet.",
               "You don't need to do anything right now."),
        "te": ("అందింది", "మీ క్లెయిమ్ మాకు అందింది. దాన్ని పరిశీలించడం ఇంకా మొదలుకాలేదు.",
               "ప్రస్తుతం మీరు ఏమీ చేయాల్సిన అవసరం లేదు."),
        "hi": ("प्राप्त हुआ", "आपका क्लेम हमें मिल गया है। इसकी जाँच अभी शुरू नहीं हुई है।",
               "अभी आपको कुछ करने की ज़रूरत नहीं है।"),
    },
    "UNDER_PROCESSING": {
        "en": ("Under processing", "Your claim is being reviewed right now. No final result yet.",
               "You don't need to do anything. Check back later for an update."),
        "te": ("పరిశీలనలో ఉంది", "మీ క్లెయిమ్‌ను ఇప్పుడు పరిశీలిస్తున్నారు. తుది ఫలితం ఇంకా రాలేదు.",
               "మీరు ఏమీ చేయాల్సిన అవసరం లేదు. కొంత సమయం తర్వాత మళ్లీ చూడండి."),
        "hi": ("जाँच चल रही है", "आपके क्लेम की अभी जाँच हो रही है। अंतिम नतीजा अभी नहीं आया है।",
               "आपको कुछ करने की ज़रूरत नहीं है। थोड़ी देर बाद दोबारा देखें।"),
    },
    "PENDING_INFORMATION": {
        "en": ("Pending information", "Your claim is on hold because more information is needed. It has not been rejected.",
               "Check the note on your claim. If you're not sure what is needed, ask your provider or a support person."),
        "te": ("సమాచారం కోసం వేచి ఉంది", "మరికొంత సమాచారం అవసరం కాబట్టి మీ క్లెయిమ్ ఆగి ఉంది. ఇది తిరస్కరించబడలేదు.",
               "మీ క్లెయిమ్‌పై ఉన్న నోట్ చూడండి. ఏమి కావాలో తెలియకపోతే మీ డాక్టర్ కార్యాలయాన్ని లేదా సపోర్ట్ ప్రతినిధిని అడగండి."),
        "hi": ("जानकारी का इंतज़ार", "आपका क्लेम रुका हुआ है क्योंकि कुछ और जानकारी चाहिए। इसे अस्वीकार नहीं किया गया है।",
               "अपने क्लेम का नोट देखें। अगर समझ न आए कि क्या चाहिए, तो अपने डॉक्टर के ऑफिस या सपोर्ट प्रतिनिधि से पूछें।"),
    },
    "PROCESSED_PAID": {
        "en": ("Processed – paid", "The review is finished and a payment was issued.",
               "You don't need to do anything. You can see the details on the My claims screen."),
        "te": ("పూర్తయింది – చెల్లించబడింది", "పరిశీలన పూర్తయింది, చెల్లింపు జరిగింది.",
               "మీరు ఏమీ చేయాల్సిన అవసరం లేదు. వివరాలు My claims స్క్రీన్‌లో చూడవచ్చు."),
        "hi": ("पूरा हुआ – भुगतान किया गया", "जाँच पूरी हो गई है और भुगतान कर दिया गया है।",
               "आपको कुछ करने की ज़रूरत नहीं है। पूरी जानकारी My claims स्क्रीन पर देख सकते हैं।"),
    },
    "PROCESSED_DENIED": {
        "en": ("Processed – denied", "The review is finished and this claim was not paid.",
               "Check the note on your claim. If you disagree, you can ask how to appeal. An appeal means asking for the decision to be looked at again."),
        "te": ("పూర్తయింది – తిరస్కరించబడింది", "పరిశీలన పూర్తయింది, ఈ క్లెయిమ్ చెల్లించబడలేదు.",
               "మీ క్లెయిమ్‌పై ఉన్న నోట్ చూడండి. మీరు అంగీకరించకపోతే అప్పీల్ ఎలా చేయాలో అడగవచ్చు. అప్పీల్ అంటే నిర్ణయాన్ని మళ్లీ పరిశీలించమని కోరడం."),
        "hi": ("पूरा हुआ – अस्वीकार", "जाँच पूरी हो गई है और इस क्लेम का भुगतान नहीं हुआ।",
               "अपने क्लेम का नोट देखें। अगर आप सहमत नहीं हैं, तो अपील के बारे में पूछ सकते हैं। अपील का मतलब है फ़ैसले की दोबारा जाँच का अनुरोध।"),
    },
}

WORDS: dict[str, dict[str, str]] = {
    "claim_heading": {"en": "Here is your claim {number}:", "te": "మీ క్లెయిమ్ {number} వివరాలు:", "hi": "आपके क्लेम {number} की जानकारी:"},
    "claims_heading": {"en": "Here are your {count} most recent claims:", "te": "మీ ఇటీవలి {count} క్లెయిమ్‌లు:", "hi": "आपके हाल के {count} क्लेम:"},
    "status": {"en": "Status", "te": "స్థితి", "hi": "स्थिति"},
    "submitted": {"en": "Submitted", "te": "సమర్పించిన తేదీ", "hi": "जमा करने की तारीख"},
    "updated": {"en": "Last updated", "te": "చివరి అప్‌డేట్", "hi": "पिछला अपडेट"},
    "note": {"en": "Note on your claim", "te": "మీ క్లెయిమ్‌పై నోట్", "hi": "क्लेम पर नोट"},
    "means": {"en": "What this means", "te": "దీని అర్థం", "hi": "इसका मतलब"},
    "next": {"en": "What you should do next", "te": "తర్వాత మీరు ఏమి చేయాలి", "hi": "आगे आपको क्या करना है"},
    "more": {"en": "More detail from the claims guide", "te": "క్లెయిమ్స్ గైడ్‌లో మరిన్ని వివరాలు", "hi": "क्लेम गाइड में और जानकारी"},
    "benefits_heading": {"en": "Here is what your {plan} record shows:", "te": "మీ {plan} రికార్డులో ఉన్న వివరాలు:", "hi": "आपके {plan} रिकॉर्ड में यह जानकारी है:"},
    "benefits_heading_staff": {"en": "Here is what the {plan} record shows:", "te": "{plan} రికార్డులో ఉన్నది:", "hi": "{plan} के रिकॉर्ड में यह है:"},
    "in_network": {"en": "You pay at in-network providers", "te": "నెట్‌వర్క్‌లోని ఆసుపత్రులు/డాక్టర్ల వద్ద మీరు చెల్లించేది", "hi": "नेटवर्क के अंदर के डॉक्टर/अस्पताल में आप देंगे"},
    "out_network": {"en": "You pay outside the network", "te": "నెట్‌వర్క్ బయట మీరు చెల్లించేది", "hi": "नेटवर्क के बाहर आप देंगे"},
    "limit": {"en": "Limit", "te": "పరిమితి", "hi": "सीमा"},
    "needs_approval": {"en": "Approval needed first: yes", "te": "ముందుగా అనుమతి అవసరం: అవును", "hi": "पहले अनुमति ज़रूरी: हाँ"},
    "not_listed": {"en": "not listed", "te": "నమోదు కాలేదు", "hi": "दर्ज नहीं"},
    "no_benefits": {"en": "Your {plan} record has no saved details for that.", "te": "మీ {plan} రికార్డులో దీని వివరాలు లేవు.", "hi": "आपके {plan} रिकॉर्ड में इसकी जानकारी नहीं है।"},
    "benefits_note": {
        "en": '"Not listed" means the record has no value. This shows what is recorded. It is not a promise that a service will be covered.',
        "te": '"నమోదు కాలేదు" అంటే రికార్డులో ఆ వివరం లేదు. ఇది నమోదైన సమాచారం మాత్రమే. ఏదైనా సేవ కవర్ అవుతుందని ఇది హామీ కాదు.',
        "hi": '"दर्ज नहीं" का मतलब है कि रिकॉर्ड में यह जानकारी नहीं है। यह सिर्फ़ दर्ज जानकारी है। यह गारंटी नहीं है कि कोई सेवा कवर होगी।',
    },
    "requirements_heading": {"en": "For a {name} request, these things are needed:", "te": "{name} అభ్యర్థన కోసం ఇవి అవసరం:", "hi": "{name} के अनुरोध के लिए ये चीज़ें चाहिए:"},
    "requirements_why": {
        "en": "Why? The review team needs them to understand the request.",
        "te": "ఎందుకు? అభ్యర్థనను అర్థం చేసుకోవడానికి పరిశీలన బృందానికి ఇవి అవసరం.",
        "hi": "क्यों? अनुरोध को समझने के लिए समीक्षा टीम को ये चाहिए।",
    },
    "requirements_next": {
        "en": "Your doctor's office can usually provide these. You can add them on the Documents screen, and I can check them for you.",
        "te": "ఇవి సాధారణంగా మీ డాక్టర్ కార్యాలయం నుండి లభిస్తాయి. వీటిని Documents స్క్రీన్‌లో అప్‌లోడ్ చేయవచ్చు. తర్వాత నేను వాటిని చెక్ చేయగలను.",
        "hi": "ये आमतौर पर आपके डॉक्टर के ऑफिस से मिल जाते हैं। इन्हें Documents स्क्रीन पर अपलोड करें, फिर मैं इन्हें जाँच सकता हूँ।",
    },
    "not_approval": {
        "en": "Having everything ready is not an approval or a denial. A person makes that decision.",
        "te": "అన్నీ సిద్ధంగా ఉండటం అంటే ఆమోదం లేదా తిరస్కరణ కాదు. ఆ నిర్ణయం ఒక వ్యక్తి తీసుకుంటారు.",
        "hi": "सब कुछ तैयार होने का मतलब मंज़ूरी या अस्वीकृति नहीं है। यह फ़ैसला एक व्यक्ति करता है।",
    },
    "readiness_incomplete": {
        "en": "Some information needed to review your request is still missing.",
        "te": "మీ అభ్యర్థనను పరిశీలించడానికి అవసరమైన కొంత సమాచారం ఇంకా లేదు.",
        "hi": "आपके अनुरोध की समीक्षा के लिए ज़रूरी कुछ जानकारी अभी नहीं मिली है।",
    },
    "readiness_manual": {
        "en": "Everything the system can check is here, and now a person needs to review it.",
        "te": "సిస్టమ్ చెక్ చేయగలిగినవన్నీ ఉన్నాయి. ఇప్పుడు ఒక వ్యక్తి పరిశీలించాలి.",
        "hi": "सिस्टम जो जाँच सकता है वह सब मौजूद है। अब एक व्यक्ति को इसे देखना होगा।",
    },
    "readiness_complete": {
        "en": "Your documents appear to have everything needed for review.",
        "te": "పరిశీలనకు అవసరమైనవన్నీ మీ డాక్యుమెంట్లలో ఉన్నట్లు కనిపిస్తోంది.",
        "hi": "लगता है समीक्षा के लिए ज़रूरी सब कुछ आपके दस्तावेज़ों में है।",
    },
    "readiness_checked": {"en": "I checked {files} for: {name}.", "te": "{name} కోసం {files} చెక్ చేశాను.", "hi": "मैंने {name} के लिए {files} की जाँच की।"},
    "SATISFIED": {"en": "Already there", "te": "ఇప్పటికే ఉన్నవి", "hi": "जो मौजूद है"},
    "MISSING": {"en": "Still needed", "te": "ఇంకా కావాల్సినవి", "hi": "अभी चाहिए"},
    "UNREADABLE": {"en": "Couldn't be read", "te": "చదవలేకపోయినవి", "hi": "जो पढ़ा नहीं जा सका"},
    "NEEDS_MANUAL_REVIEW": {"en": "A person needs to check", "te": "ఒక వ్యక్తి చెక్ చేయాలి", "hi": "इसे एक व्यक्ति देखेगा"},
    "readiness_next_heading": {"en": "What happens next?", "te": "తర్వాత ఏమి జరుగుతుంది?", "hi": "आगे क्या होगा?"},
    "readiness_next_1": {
        "en": "Ask your healthcare provider for the missing details. Medical information has to come from them.",
        "te": "లేని వివరాల కోసం మీ డాక్టర్ కార్యాలయాన్ని అడగండి. వైద్య సమాచారం వారి నుండే రావాలి.",
        "hi": "जो जानकारी नहीं है, उसके लिए अपने डॉक्टर के ऑफिस से पूछें। मेडिकल जानकारी उन्हीं से मिलेगी।",
    },
    "readiness_next_2": {
        "en": "Once you have them, upload them on the Documents screen and ask me to check again.",
        "te": "అవి లభించాక Documents స్క్రీన్‌లో అప్‌లోడ్ చేసి, మళ్లీ చెక్ చేయమని నన్ను అడగండి.",
        "hi": "जानकारी मिलने पर उसे Documents स्क्रीन पर अपलोड करें और मुझे दोबारा जाँचने को कहें।",
    },
    "readiness_not_rejected": {
        "en": "Please note: missing information does not mean your request was rejected.",
        "te": "గమనిక: సమాచారం లేకపోవడం అంటే మీ అభ్యర్థన తిరస్కరించబడిందని కాదు.",
        "hi": "ध्यान दें: जानकारी कम होने का मतलब यह नहीं कि आपका अनुरोध अस्वीकार हो गया।",
    },
    "found_heading": {"en": "Here's what I found in your plan documents:", "te": "మీ ప్లాన్ డాక్యుమెంట్లలో నాకు దొరికినది:", "hi": "आपके प्लान दस्तावेज़ों में मुझे यह मिला:"},
    "found_heading_staff": {"en": "Here's what I found in the documents:", "te": "డాక్యుమెంట్లలో నాకు దొరికినది:", "hi": "दस्तावेज़ों में मुझे यह मिला:"},
    "found_next": {
        "en": "Want this explained more simply? Just say \"I don't understand\". You can also ask for a support person.",
        "te": "ఇంకా సులభంగా వివరించాలా? \"అర్థం కాలేదు\" అని చెప్పండి. సపోర్ట్ ప్రతినిధిని కూడా అడగవచ్చు.",
        "hi": "क्या इसे और आसान भाषा में समझाऊँ? बस \"समझ नहीं आया\" कहें। आप सपोर्ट प्रतिनिधि से भी बात कर सकते हैं।",
    },
    "doc_heading": {"en": "", "te": "మీ డాక్యుమెంట్ నుండి సమాచారం (డాక్యుమెంట్‌లో ఉన్నట్లే ఇంగ్లీష్‌లో చూపిస్తున్నాను):", "hi": "आपके दस्तावेज़ से जानकारी (जैसी दस्तावेज़ में है, अंग्रेज़ी में):"},
    "english_note": {
        "en": "",
        "te": "గమనిక: ఈ భాగం ప్రస్తుతం ఇంగ్లీష్‌లోనే ఉంది, ఎందుకంటే అనువాద సేవ అందుబాటులో లేదు.",
        "hi": "ध्यान दें: यह हिस्सा अभी अंग्रेज़ी में है, क्योंकि अनुवाद सेवा उपलब्ध नहीं है।",
    },
    "terms_heading": {"en": "What these words mean", "te": "ఈ పదాల అర్థం", "hi": "इन शब्दों का मतलब"},
    "simplify_heading": {"en": "No problem. Here it is in simple words:", "te": "పర్వాలేదు. సులభమైన మాటల్లో చెబుతాను:", "hi": "कोई बात नहीं। आसान शब्दों में समझाता हूँ:"},
    "simplify_short": {
        "en": "No problem. Tell me which part was confusing, or pick what you'd like help with:",
        "te": "పర్వాలేదు. ఏ భాగం అర్థం కాలేదో చెప్పండి, లేదా మీకు కావాల్సినది ఎంచుకోండి:",
        "hi": "कोई बात नहीं। बताइए कौन-सा हिस्सा समझ नहीं आया, या नीचे से चुनें:",
    },
    "guide_provider": {
        "en": "Hello! I can help with prior authorization paperwork, plan benefits and the documents you've uploaded. What do you need?",
        "te": "నమస్కారం! ప్రియర్ ఆథరైజేషన్ పత్రాలు, ప్లాన్ ప్రయోజనాలు, మీరు అప్‌లోడ్ చేసిన డాక్యుమెంట్ల విషయంలో సహాయం చేస్తాను. మీకు ఏమి కావాలి?",
        "hi": "नमस्ते! मैं प्रायर ऑथराइज़ेशन के काग़ज़ात, प्लान के लाभ और आपके अपलोड किए दस्तावेज़ों में मदद कर सकता हूँ। आपको क्या चाहिए?",
    },
    "guide_agent": {
        "en": "Hello! I can help with support procedures, plan details and what the documents say. Your cases are in the Case queue.",
        "te": "నమస్కారం! సపోర్ట్ విధానాలు, ప్లాన్ వివరాలు, డాక్యుమెంట్ల సమాచారం విషయంలో సహాయం చేస్తాను. మీ కేసులు Case queue లో ఉన్నాయి.",
        "hi": "नमस्ते! मैं सपोर्ट प्रक्रियाओं, प्लान की जानकारी और दस्तावेज़ों में मदद कर सकता हूँ। आपके केस Case queue में हैं।",
    },
    "guide_admin": {
        "en": "Hello! I can answer questions about plans and documents. Numbers and logs are on the Admin dashboard, and accounts are on the Users screen.",
        "te": "నమస్కారం! ప్లాన్లు, డాక్యుమెంట్ల గురించి సమాధానం ఇవ్వగలను. గణాంకాలు, లాగ్‌లు Admin dashboard లో, ఖాతాలు Users స్క్రీన్‌లో ఉన్నాయి.",
        "hi": "नमस्ते! मैं प्लान और दस्तावेज़ों के सवालों के जवाब दे सकता हूँ। आँकड़े और लॉग Admin dashboard पर हैं, और खाते Users स्क्रीन पर हैं।",
    },
    "guide_general": {
        "en": "Hello! I can help with your claims, plan costs and documents. What would you like to know?",
        "te": "పర్వాలేదు! నేను అర్థమయ్యేలా చెబుతాను. మీరు ఏమి తెలుసుకోవాలనుకుంటున్నారు?",
        "hi": "कोई बात नहीं! मैं समझाने में मदद करूँगा। आप क्या जानना चाहते हैं?",
    },
    "coverage_note": {
        "en": "This doesn't confirm that it's covered. If you need a clear yes or no, a support person can check.",
        "te": "ఇది కవర్ అవుతుందని ఇది నిర్ధారించదు. స్పష్టమైన సమాధానం కావాలంటే సపోర్ట్ ప్రతినిధి చెక్ చేయగలరు.",
        "hi": "इससे यह पक्का नहीं होता कि यह कवर है। साफ़ जवाब के लिए सपोर्ट प्रतिनिधि जाँच कर सकते हैं।",
    },
    "guide_authorization": {
        "en": "Prior authorization means asking your plan to review a service before you get it.\n\nHow it works:\n1. Your doctor's office prepares the request and documents.\n2. A person on the review team looks at them.\n3. If something is missing, they ask for it. That doesn't mean a rejection.\n\nI can show what's needed, but I can't approve or deny a request. Which procedure is it for?",
        "te": "ప్రియర్ ఆథరైజేషన్ అంటే ఒక సేవ తీసుకునే ముందు దాన్ని పరిశీలించమని మీ ప్లాన్‌ను కోరడం.\n\nఇది ఎలా జరుగుతుంది:\n1. మీ డాక్టర్ కార్యాలయం అభ్యర్థన, డాక్యుమెంట్లు సిద్ధం చేస్తుంది.\n2. పరిశీలన బృందంలోని ఒక వ్యక్తి వాటిని చూస్తారు.\n3. ఏదైనా లేకపోతే అడుగుతారు. అంటే తిరస్కరణ అని కాదు.\n\nఏమి కావాలో నేను చూపించగలను, కానీ అభ్యర్థనను ఆమోదించలేను లేదా తిరస్కరించలేను. ఇది ఏ చికిత్స/పరీక్ష కోసం?",
        "hi": "प्रायर ऑथराइज़ेशन का मतलब है कोई सेवा लेने से पहले अपने प्लान से उसकी जाँच करवाना।\n\nयह कैसे होता है:\n1. आपके डॉक्टर का ऑफिस अनुरोध और दस्तावेज़ तैयार करता है।\n2. समीक्षा टीम का एक व्यक्ति उन्हें देखता है।\n3. अगर कुछ कम हो, तो वे माँगते हैं। इसका मतलब अस्वीकृति नहीं है।\n\nमैं बता सकता हूँ कि क्या चाहिए, लेकिन अनुरोध को मंज़ूर या अस्वीकार नहीं कर सकता। यह किस जाँच या इलाज के लिए है?",
    },
    "guide_procedures": {
        "en": "Sure. Which procedure is it for?",
        "te": "తప్పకుండా. ఇది ఏ చికిత్స/పరీక్ష కోసం?",
        "hi": "ज़रूर। यह किस जाँच या इलाज के लिए है?",
    },
    "opt_covers": {"en": "What my plan covers", "te": "నా ప్లాన్ ఏమి కవర్ చేస్తుంది", "hi": "मेरा प्लान क्या कवर करता है"},
    "opt_pay": {"en": "How much I may need to pay", "te": "నేను ఎంత చెల్లించాలి", "hi": "मुझे कितना देना पड़ सकता है"},
    "opt_claim": {"en": "How to check my claim", "te": "నా క్లెయిమ్ ఎలా చూడాలి", "hi": "अपना क्लेम कैसे देखें"},
    "opt_documents": {"en": "Which documents I need", "te": "నాకు ఏ డాక్యుమెంట్లు కావాలి", "hi": "मुझे कौन-से दस्तावेज़ चाहिए"},
    "opt_person": {"en": "Talk to a support person", "te": "సపోర్ట్ ప్రతినిధితో మాట్లాడాలి", "hi": "सपोर्ट प्रतिनिधि से बात करनी है"},
}

# Plain wording for stored requirement descriptions; anything not listed is shown as stored.
REQUIREMENTS: dict[str, dict[str, str]] = {
    "Requested service date present": {"en": "The date you want the service", "te": "సేవ కావాల్సిన తేదీ", "hi": "सेवा की तारीख"},
    "Ordering provider identifier present in synthetic format": {"en": "Your doctor's 10-digit provider number", "te": "మీ డాక్టర్ 10 అంకెల ప్రొవైడర్ నంబర్", "hi": "आपके डॉक्टर का 10 अंकों का प्रोवाइडर नंबर"},
    "Conservative therapy duration is documented": {"en": "How long you tried other treatment first, like physical therapy", "te": "ముందుగా ఫిజియోథెరపీ వంటి ఇతర చికిత్స ఎంత కాలం తీసుకున్నారో", "hi": "पहले फिजियोथेरेपी जैसा दूसरा इलाज कितने समय तक लिया"},
    "Medical therapy duration is documented": {"en": "How long you tried medicine or other treatment first", "te": "ముందుగా మందులు లేదా ఇతర చికిత్స ఎంత కాలం తీసుకున్నారో", "hi": "पहले दवा या दूसरा इलाज कितने समय तक लिया"},
    "Member number present in synthetic format": {"en": "Your member number, written like SYN-M-000000", "te": "మీ మెంబర్ నంబర్ (SYN-M-000000 రూపంలో)", "hi": "आपका मेंबर नंबर (SYN-M-000000 जैसा)"},
    "Member number present": {"en": "Your member number", "te": "మీ మెంబర్ నంబర్", "hi": "आपका मेंबर नंबर"},
    "Referral letter included": {"en": "A referral letter from your doctor", "te": "మీ డాక్టర్ నుండి రిఫరల్ లెటర్", "hi": "आपके डॉक्टर का रेफ़रल लेटर"},
    "Referral dated within 30 days before request": {"en": "A referral dated within 30 days before your request", "te": "అభ్యర్థనకు 30 రోజుల లోపు తేదీ ఉన్న రిఫరల్", "hi": "अनुरोध से 30 दिन के अंदर की तारीख वाला रेफ़रल"},
    "Clinical note summary included": {"en": "A short note from your doctor about your care", "te": "మీ చికిత్స గురించి డాక్టర్ రాసిన చిన్న నోట్", "hi": "आपके इलाज के बारे में डॉक्टर का छोटा नोट"},
    "Supporting rationale reviewed by authorized staff": {"en": "The reason the service is needed (a staff member reads this)", "te": "ఈ సేవ ఎందుకు అవసరమో కారణం (సిబ్బంది దీన్ని చదువుతారు)", "hi": "सेवा क्यों ज़रूरी है, इसका कारण (इसे स्टाफ़ पढ़ता है)"},
    "Visit history reviewed by authorized staff": {"en": "Your visit history for this year (a staff member reads this)", "te": "ఈ సంవత్సరం మీ విజిట్ల చరిత్ర (సిబ్బంది దీన్ని చదువుతారు)", "hi": "इस साल की आपकी विज़िट का रिकॉर्ड (इसे स्टाफ़ पढ़ता है)"},
}

# (English pattern, then Telugu/Hindi meaning). General meanings only: never a plan-specific value.
GLOSSARY: tuple[tuple[str, dict[str, str]], ...] = (
    (r"\bco-?pays?\b", {"en": "Copay: a fixed amount you pay for a visit or service.", "te": "కోపే: ఒక విజిట్ లేదా సేవకు మీరు చెల్లించే నిర్ణీత మొత్తం.", "hi": "कोपे: किसी विज़िट या सेवा के लिए आपकी तय रकम।"}),
    (r"\bdeductibles?\b", {"en": "Deductible: what you pay yourself each year before your plan starts sharing costs.", "te": "డిడక్టిబుల్: ప్లాన్ ఖర్చులో భాగం పంచుకోవడం మొదలయ్యే ముందు ప్రతి సంవత్సరం మీరే చెల్లించే మొత్తం.", "hi": "डिडक्टिबल: प्लान के खर्च बाँटने से पहले हर साल आपकी अपनी दी जाने वाली रकम।"}),
    (r"\bcoinsurance\b", {"en": "Coinsurance: your share of a bill, as a percentage.", "te": "కోఇన్సూరెన్స్: బిల్లులో మీ వాటా, శాతం రూపంలో.", "hi": "कोइंश्योरेंस: बिल में आपका हिस्सा, प्रतिशत में।"}),
    (r"\bprior auth\w*|\bpre-?authori[sz]ation\b", {"en": "Prior authorization: getting approval from the plan before a service.", "te": "ప్రియర్ ఆథరైజేషన్: సేవ తీసుకునే ముందు ప్లాన్ నుండి అనుమతి పొందడం.", "hi": "प्रायर ऑथराइज़ेशन: सेवा लेने से पहले प्लान से अनुमति लेना।"}),
    (r"\bout[- ]of[- ]pocket\b", {"en": "Out-of-pocket maximum: the most you pay in a plan year for covered in-network care.", "te": "అవుట్-ఆఫ్-పాకెట్ గరిష్ట పరిమితి: ఒక ప్లాన్ సంవత్సరంలో నెట్‌వర్క్‌లోని కవర్ అయ్యే సేవలకు మీరు చెల్లించే గరిష్ట మొత్తం.", "hi": "आउट-ऑफ़-पॉकेट अधिकतम सीमा: एक प्लान वर्ष में नेटवर्क की कवर की गई सेवाओं के लिए आपकी सबसे ज़्यादा दी जाने वाली रकम।"}),
    (r"\bout[- ]of[- ]network\b", {"en": "Out of network: doctors or hospitals without an agreement with your plan, which can cost you more.", "te": "అవుట్-ఆఫ్-నెట్‌వర్క్: మీ ప్లాన్‌తో ఒప్పందం లేని డాక్టర్లు/ఆసుపత్రులు. ఖర్చు ఎక్కువ కావచ్చు.", "hi": "आउट-ऑफ़-नेटवर्क: जिन डॉक्टरों/अस्पतालों का आपके प्लान से समझौता नहीं है। खर्च ज़्यादा हो सकता है।"}),
    (r"\bin[- ]network\b", {"en": "In network: doctors or hospitals with an agreement with your plan.", "te": "ఇన్-నెట్‌వర్క్: మీ ప్లాన్‌తో ఒప్పందం ఉన్న డాక్టర్లు/ఆసుపత్రులు.", "hi": "इन-नेटवर्क: जिन डॉक्टरों/अस्पतालों का आपके प्लान से समझौता है।"}),
    (r"\bappeal", {"en": "Appeal: asking for a decision to be looked at again.", "te": "అప్పీల్: ఒక నిర్ణయాన్ని మళ్లీ పరిశీలించమని కోరడం.", "hi": "अपील: किसी फ़ैसले की दोबारा जाँच का अनुरोध।"}),
    (r"\breferrals?\b", {"en": "Referral: a doctor's request for you to see another doctor or get a service.", "te": "రిఫరల్: మరో డాక్టర్‌ను కలవమని లేదా ఒక సేవ తీసుకోమని డాక్టర్ ఇచ్చే సూచన.", "hi": "रेफ़रल: दूसरे डॉक्टर से मिलने या सेवा लेने के लिए डॉक्टर की सिफ़ारिश।"}),
)

# Fixed assistant messages, matched by their English text. "en": None keeps the pipeline's own wording.
FIXED: tuple[tuple[str, dict[str, str | None]], ...] = (
    (r"^I couldn't find information about this", {
        "en": "I want to make sure you get the correct information. I couldn't confidently answer this using the information available, so I won't guess. You can try one of the options here, or our support team can help, and they won't need you to explain everything again.",
        "te": "మీకు సరైన సమాచారం అందాలని నా ఉద్దేశం. అందుబాటులో ఉన్న సమాచారంతో నేను దీనికి నమ్మకంగా సమాధానం చెప్పలేకపోతున్నాను, అందుకే ఊహించి చెప్పను. మా సపోర్ట్ టీమ్‌ను సంప్రదించడంలో సహాయం చేస్తాను. మీరు అంతా మళ్లీ చెప్పాల్సిన అవసరం ఉండదు.",
        "hi": "मैं चाहता हूँ कि आपको सही जानकारी मिले। उपलब्ध जानकारी से मैं इसका भरोसेमंद जवाब नहीं दे पा रहा, इसलिए अनुमान नहीं लगाऊँगा। मैं सपोर्ट टीम से जुड़ने में मदद कर सकता हूँ। आपको सब कुछ दोबारा नहीं बताना पड़ेगा।",
    }),
    (r"^Your plan is (?P<plan>.+?)\. Your member number is (?P<number>\S+)\.$", {
        "en": None,
        "te": "మీ ప్లాన్ {plan}. మీ మెంబర్ నంబర్ {number}.",
        "hi": "आपका प्लान {plan} है। आपका मेंबर नंबर {number} है।",
    }),
    (r"^The only matching information", {
        "en": None,
        "te": "నాకు దొరికిన సమాచారం పాత వెర్షన్‌లో ఉంది, కాబట్టి దానిపై ఆధారపడలేను. ప్రస్తుత నియమాలను సపోర్ట్ ప్రతినిధి నిర్ధారించగలరు.",
        "hi": "जो जानकारी मिली वह पुराने संस्करण की है, इसलिए उस पर भरोसा नहीं कर सकता। मौजूदा नियम सपोर्ट प्रतिनिधि बता सकते हैं।",
    }),
    (r"^I can't share my configuration", {
        "en": None,
        "te": "నా సెట్టింగ్‌లు లేదా ఇతరుల సమాచారం పంచుకోలేను. మీ క్లెయిమ్‌లు, మీ ప్లాన్, డాక్యుమెంట్లు మరియు సపోర్ట్ విషయంలో సహాయం చేయగలను.",
        "hi": "मैं अपनी सेटिंग्स या दूसरों की जानकारी साझा नहीं कर सकता। मैं आपके क्लेम, प्लान, दस्तावेज़ और सपोर्ट में मदद कर सकता हूँ।",
    }),
    (r"^I can't give medical advice", {
        "en": None,
        "te": "నేను వైద్య సలహా, రోగ నిర్ధారణ లేదా చికిత్స సూచనలు ఇవ్వలేను. దయచేసి డాక్టర్‌ను సంప్రదించండి. ప్రయోజనాలు, క్లెయిమ్‌లు, అవసరమైన డాక్యుమెంట్ల విషయంలో సహాయం చేయగలను.",
        "hi": "मैं मेडिकल सलाह, बीमारी की पहचान या इलाज की सलाह नहीं दे सकता। कृपया डॉक्टर से मिलें। मैं लाभ, क्लेम और ज़रूरी दस्तावेज़ों में मदद कर सकता हूँ।",
    }),
    (r"^I can't see account-specific", {
        "en": None,
        "te": "చెల్లింపు తేదీలు, బ్యాలెన్స్ లేదా అనుమతి నిర్ణయాలు వంటి ఖాతా వివరాలు నేను చూడలేను. మీ క్లెయిమ్ రికార్డులు, ప్లాన్ ప్రయోజనాలు చూపించగలను.",
        "hi": "मैं भुगतान की तारीख, बैलेंस या अनुमति के फ़ैसले जैसी खाते की जानकारी नहीं देख सकता। मैं आपके क्लेम रिकॉर्ड और प्लान के लाभ दिखा सकता हूँ।",
    }),
    (r"^You can see the current status", {
        "en": None,
        "te": "మీ సపోర్ట్ కేసుల స్థితి మరియు చరిత్ర Support cases స్క్రీన్‌లో చూడవచ్చు.",
        "hi": "आपके सपोर्ट केस की स्थिति और इतिहास Support cases स्क्रीन पर देख सकते हैं।",
    }),
    (r"^I couldn't find a claim", {
        "en": None,
        "te": "ఆ నంబర్‌తో మీ ఖాతాలో క్లెయిమ్ కనిపించలేదు. దయచేసి నంబర్‌ను మళ్లీ చూడండి.",
        "hi": "इस नंबर का कोई क्लेम आपके खाते में नहीं मिला। कृपया नंबर दोबारा देखें।",
    }),
    (r"^Which claim do you mean", {
        "en": None,
        "te": "ఏ క్లెయిమ్ గురించి అడుగుతున్నారు? దయచేసి క్లెయిమ్ నంబర్ చెప్పండి, ఉదాహరణకు SYN-CLM-2026-000101.",
        "hi": "आप किस क्लेम की बात कर रहे हैं? कृपया क्लेम नंबर बताएँ, जैसे SYN-CLM-2026-000101।",
    }),
    (r"^You have no claims", {
        "en": None, "te": "మీ ఖాతాలో క్లెయిమ్‌లు ఏమీ లేవు.", "hi": "आपके खाते में कोई क्लेम नहीं है।",
    }),
    (r"^Your account can't look up", {
        "en": None,
        "te": "మీ ఖాతాకు ఈ వివరాలు చూసే అనుమతి లేదు.",
        "hi": "आपके खाते को यह जानकारी देखने की अनुमति नहीं है।",
    }),
    (r"^Which plan do you mean", {
        "en": None,
        "te": "ఏ ప్లాన్ గురించి అడుగుతున్నారు? దయచేసి ప్లాన్ కోడ్ చెప్పండి, ఉదాహరణకు SYN-PLAN-GOLD-01.",
        "hi": "आप किस प्लान की बात कर रहे हैं? कृपया प्लान कोड बताएँ, जैसे SYN-PLAN-GOLD-01।",
    }),
    (r"^No active plan", {
        "en": None, "te": "ఆ కోడ్‌తో మీకు అందుబాటులో ఉన్న ప్లాన్ లేదు.", "hi": "इस कोड का कोई प्लान आपके लिए उपलब्ध नहीं है।",
    }),
    (r"^I couldn't complete the", {
        "en": None,
        "te": "ఇప్పుడు ఈ పని పూర్తి చేయలేకపోయాను, కాబట్టి చూపించడానికి ఫలితం లేదు. దయచేసి తర్వాత ప్రయత్నించండి, లేదా సపోర్ట్ ప్రతినిధిని అడగండి.",
        "hi": "अभी यह काम पूरा नहीं हो सका, इसलिए दिखाने को कोई नतीजा नहीं है। कृपया बाद में कोशिश करें या सपोर्ट प्रतिनिधि से पूछें।",
    }),
    (r"^You haven't uploaded any documents", {
        "en": None,
        "te": "మీరు ఇంకా డాక్యుమెంట్లు అప్‌లోడ్ చేయలేదు. Documents స్క్రీన్‌లో అప్‌లోడ్ చేసి, తర్వాత నన్ను అడగండి.",
        "hi": "आपने अभी कोई दस्तावेज़ अपलोड नहीं किया है। Documents स्क्रीन पर अपलोड करें, फिर मुझसे पूछें।",
    }),
    (r"^None of your uploaded documents mention (?P<name>.+?)\.", {
        "en": None,
        "te": "మీరు అప్‌లోడ్ చేసిన డాక్యుమెంట్లలో {name} పేరు లేదు. మీ ఖాతా నుండి అప్‌లోడ్ చేసినవి మాత్రమే నేను చదవగలను.",
        "hi": "आपके अपलोड किए दस्तावेज़ों में {name} का नाम नहीं है। मैं सिर्फ़ आपके खाते से अपलोड किए गए दस्तावेज़ पढ़ सकता हूँ।",
    }),
    (r"^I couldn't find an uploaded document", {
        "en": None, "te": "ఆ పేరుతో అప్‌లోడ్ చేసిన డాక్యుమెంట్ మీ ఖాతాలో లేదు.", "hi": "इस नाम का कोई दस्तावेज़ आपके खाते में नहीं मिला।",
    }),
    (r"^I found your document but couldn't read", {
        "en": None,
        "te": "మీ డాక్యుమెంట్ దొరికింది, కానీ అందులోని అక్షరాలు చదవలేకపోయాను. స్కాన్ చేసిన పేజీలకు OCR కావాలి, అది ఇక్కడ అందుబాటులో లేదు. నేను ఏమీ ఊహించలేదు.",
        "hi": "आपका दस्तावेज़ मिला, लेकिन उसका टेक्स्ट पढ़ा नहीं जा सका। स्कैन किए गए पेजों के लिए OCR चाहिए, जो यहाँ उपलब्ध नहीं है। मैंने कोई अनुमान नहीं लगाया।",
    }),
    (r"^I read (?P<files>.+?) but didn't find that", {
        "en": None,
        "te": "{files} చదివాను, కానీ ఆ వివరం కనిపించలేదు. ఊహించి చెప్పను. సపోర్ట్ ప్రతినిధి సహాయం చేయగలరు.",
        "hi": "मैंने {files} पढ़ा, लेकिन यह जानकारी नहीं मिली। मैं अनुमान नहीं लगाऊँगा। सपोर्ट प्रतिनिधि मदद कर सकते हैं।",
    }),
    (r"^Your account doesn't have", {
        "en": None, "te": "మీ ఖాతాకు ఇది అందుబాటులో లేదు.", "hi": "यह आपके खाते के लिए उपलब्ध नहीं है।",
    }),
    (r"^Which procedure (?:do you mean|should I check against)\? (?:Configured requirement sets|Configured sets): (?P<options>.+)$", {
        "en": None,
        "te": "ఏ చికిత్స/పరీక్ష కోసం చూడాలి? అందుబాటులో ఉన్నవి: {options}",
        "hi": "किस जाँच या इलाज के लिए देखूँ? उपलब्ध विकल्प: {options}",
    }),
    (r"^I've prepared a support case", {
        "en": "I've written a short summary for our support team, so you won't have to explain everything again. It has not been created yet. Please check it and choose \"Create support case\" to send it.",
        "te": "మీరు అంతా మళ్లీ చెప్పాల్సిన అవసరం లేకుండా సపోర్ట్ టీమ్ కోసం చిన్న సారాంశం సిద్ధం చేశాను. ఇంకా ఏమీ పంపలేదు. దయచేసి చూసి, పంపడానికి బటన్ నొక్కండి.",
        "hi": "मैंने सपोर्ट टीम के लिए छोटा सारांश तैयार किया है, ताकि आपको सब दोबारा न बताना पड़े। अभी कुछ भेजा नहीं गया है। कृपया देखकर बटन दबाएँ।",
    }),
    (r"^I couldn't prepare a support case", {
        "en": None,
        "te": "సపోర్ట్ కేసు సిద్ధం చేయలేకపోయాను. ఏదీ సృష్టించబడలేదు. Support cases స్క్రీన్ నుండి సృష్టించవచ్చు.",
        "hi": "सपोर्ट केस तैयार नहीं हो सका। कुछ भी नहीं बना। आप Support cases स्क्रीन से बना सकते हैं।",
    }),
)

DISCLAIMERS: dict[str, dict[str, str]] = {
    "Information comes from": {
        "te": "ఈ సమాచారం సింథటిక్ ప్రోటోటైప్ డాక్యుమెంట్ల నుండి వచ్చింది. ఇది కవరేజ్ లేదా అనుమతి నిర్ణయం కాదు.",
        "hi": "यह जानकारी सिंथेटिक प्रोटोटाइप दस्तावेज़ों से है। यह कवरेज या अनुमति का फ़ैसला नहीं है।",
    },
    "Values marked as records": {
        "te": "రికార్డు విలువలు నేరుగా సింథటిక్ డేటాబేస్ నుండి వచ్చాయి.",
        "hi": "रिकॉर्ड के मान सीधे सिंथेटिक डेटाबेस से लिए गए हैं।",
    },
    "Quoted from your uploaded": {
        "te": "ఇది మీరు అప్‌లోడ్ చేసిన డాక్యుమెంట్ నుండి తీసుకున్నది. ఇది వైద్య అభిప్రాయం లేదా కవరేజ్/అనుమతి నిర్ణయం కాదు.",
        "hi": "यह आपके अपलोड किए दस्तावेज़ से लिया गया है। यह मेडिकल राय या कवरेज/अनुमति का फ़ैसला नहीं है।",
    },
    "This came from handwriting": {
        "te": "ఇది చేతిరాత నుండి తీసుకున్నది, కంప్యూటర్ తప్పుగా చదివి ఉండవచ్చు. [?] గుర్తు ఉన్న పదాలు మరింత అస్పష్టంగా ఉన్నాయి. మందు పేరు, మోతాదు లేదా తేదీని నమ్మే ముందు మీ డాక్టర్ లేదా ఫార్మసిస్ట్‌తో సరిచూసుకోండి.",
        "hi": "यह हाथ की लिखावट से लिया गया है, और कंप्यूटर ने इसे गलत पढ़ा हो सकता है। [?] वाले शब्द ज़्यादा अस्पष्ट थे। दवा का नाम, खुराक या तारीख पर भरोसा करने से पहले अपने डॉक्टर या फ़ार्मासिस्ट से जाँच लें।",
    },
    "This checklist reviews": {
        "te": "ఈ జాబితా డాక్యుమెంట్లు పూర్తిగా ఉన్నాయా అని మాత్రమే చూస్తుంది. ఇది ఆమోదం, తిరస్కరణ లేదా కవరేజ్ హామీ కాదు. నిర్ణయం అధికారం ఉన్న వ్యక్తి తీసుకుంటారు.",
        "hi": "यह सूची सिर्फ़ यह देखती है कि दस्तावेज़ पूरे हैं या नहीं। यह मंज़ूरी, अस्वीकृति या कवरेज की गारंटी नहीं है। फ़ैसला अधिकृत व्यक्ति करता है।",
    },
}
