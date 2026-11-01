// Assistant screen wording in English, Telugu and Hindi. The rest of the portal stays in English.
// Quick actions send ordinary questions through the normal chat path, so no answer is written here.

import type { Language, Role } from "../../types/api";

export const ANSWER_LANGUAGES: { code: Language; name: string; action: string }[] = [
  { code: "en", name: "English", action: "Show in English" },
  { code: "te", name: "తెలుగు", action: "తెలుగులో చూపించు" },
  { code: "hi", name: "हिन्दी", action: "हिन्दी में दिखाएँ" },
];

export const WELCOME: Record<Role, Record<Language, string>> = {
  MEMBER: {
    en: "Hello! Welcome to your healthcare support portal. I'm your virtual healthcare assistant. I can help you understand your health plan, check claim information, find required documents, and answer your questions.\n\nHow can I help you today?",
    te: "నమస్కారం! మీ హెల్త్‌కేర్ సపోర్ట్ పోర్టల్‌కు స్వాగతం. మీ హెల్త్ ప్లాన్, క్లెయిమ్ వివరాలు, అవసరమైన డాక్యుమెంట్లు మరియు ఇతర సందేహాల గురించి తెలుసుకోవడానికి నేను సహాయం చేస్తాను.\n\nఈరోజు మీకు ఎలా సహాయం చేయగలను?",
    hi: "नमस्ते! आपके हेल्थकेयर सपोर्ट पोर्टल में आपका स्वागत है। मैं आपकी हेल्थ प्लान, क्लेम की जानकारी, ज़रूरी दस्तावेज़ और अन्य सवालों को समझने में मदद कर सकता हूँ।\n\nआज मैं आपकी कैसे सहायता कर सकता हूँ?",
  },
  PROVIDER: {
    en: "Hello! I'm your provider assistant. I can help with prior authorization paperwork, plan benefits and the documents you've uploaded.\n\nWhat do you need today?",
    te: "నమస్కారం! నేను మీ ప్రొవైడర్ అసిస్టెంట్. ప్రియర్ ఆథరైజేషన్ పత్రాలు, ప్లాన్ ప్రయోజనాలు, మీరు అప్‌లోడ్ చేసిన డాక్యుమెంట్ల విషయంలో సహాయం చేస్తాను.\n\nఈరోజు మీకు ఏమి కావాలి?",
    hi: "नमस्ते! मैं आपका प्रोवाइडर असिस्टेंट हूँ। मैं प्रायर ऑथराइज़ेशन के काग़ज़ात, प्लान के लाभ और आपके अपलोड किए दस्तावेज़ों में मदद कर सकता हूँ।\n\nआज आपको क्या चाहिए?",
  },
  SUPPORT_AGENT: {
    en: "Hello! I'm your support assistant. I can help with support procedures, plan details and what the documents say.\n\nWhat do you need to look up?",
    te: "నమస్కారం! నేను మీ సపోర్ట్ అసిస్టెంట్. సపోర్ట్ విధానాలు, ప్లాన్ వివరాలు, డాక్యుమెంట్ల సమాచారం విషయంలో సహాయం చేస్తాను.\n\nమీరు ఏమి చూడాలనుకుంటున్నారు?",
    hi: "नमस्ते! मैं आपका सपोर्ट असिस्टेंट हूँ। मैं सपोर्ट प्रक्रियाओं, प्लान की जानकारी और दस्तावेज़ों में मदद कर सकता हूँ।\n\nआप क्या देखना चाहते हैं?",
  },
  ADMIN: {
    en: "Hello! I can answer questions about plans and documents. Numbers and logs are on the Admin dashboard, and accounts are on the Users screen.\n\nWhat would you like to do?",
    te: "నమస్కారం! ప్లాన్లు, డాక్యుమెంట్ల గురించి సమాధానం ఇవ్వగలను. గణాంకాలు, లాగ్‌లు Admin dashboard లో, ఖాతాలు Users స్క్రీన్‌లో ఉన్నాయి.\n\nమీరు ఏమి చేయాలనుకుంటున్నారు?",
    hi: "नमस्ते! मैं प्लान और दस्तावेज़ों के सवालों के जवाब दे सकता हूँ। आँकड़े और लॉग Admin dashboard पर हैं, और खाते Users स्क्रीन पर हैं।\n\nआप क्या करना चाहते हैं?",
  },
};

export interface QuickAction {
  id: string;
  label: Record<Language, string>;
  message?: string; // sent to the assistant
  path?: string; // or opens a screen
}

const PLAN_BENEFITS: QuickAction = { id: "plan", message: "Show benefits for SYN-PLAN-GOLD-01", label: { en: "Gold Plan Benefits", te: "గోల్డ్ ప్లాన్ ప్రయోజనాలు", hi: "गोल्ड प्लान के लाभ" } };
const DOCUMENTS: QuickAction = { id: "documents", message: "Which documents do I need?", label: { en: "Required Documents", te: "అవసరమైన డాక్యుమెంట్లు", hi: "ज़रूरी दस्तावेज़" } };
const AUTHORIZATION: QuickAction = { id: "authorization", message: "How does prior authorization work?", label: { en: "Authorization Process", te: "అనుమతి ప్రక్రియ", hi: "अनुमति की प्रक्रिया" } };
const UPLOAD: QuickAction = { id: "upload", path: "/documents", label: { en: "Upload Medical Documents", te: "వైద్య డాక్యుమెంట్లు అప్‌లోడ్ చేయాలి", hi: "मेडिकल दस्तावेज़ अपलोड करें" } };
const PERSON: QuickAction = { id: "person", message: "I want to talk to a person", label: { en: "Talk to a Support Representative", te: "సపోర్ట్ ప్రతినిధితో మాట్లాడాలి", hi: "सपोर्ट प्रतिनिधि से बात करें" } };
const APPEALS: QuickAction = { id: "appeals", message: "How do I appeal a denied claim?", label: { en: "How Claim Appeals Work", te: "క్లెయిమ్ అప్పీల్ ఎలా పనిచేస్తుంది", hi: "क्लेम अपील कैसे होती है" } };

export const QUICK_ACTIONS: Record<Role, QuickAction[]> = {
  MEMBER: [
    { id: "benefits", message: "Show my plan benefits", label: { en: "Understand My Health Benefits", te: "నా హెల్త్ ప్రయోజనాలు తెలుసుకోవాలి", hi: "मेरे हेल्थ लाभ समझें" } },
    { id: "claims", message: "Show my claims", label: { en: "Check My Claim Status", te: "నా క్లెయిమ్ స్థితి చూడాలి", hi: "मेरे क्लेम की स्थिति देखें" } },
    DOCUMENTS,
    AUTHORIZATION,
    UPLOAD,
    { id: "request", message: "Please create a support case", label: { en: "Create a Support Request", te: "సపోర్ట్ రిక్వెస్ట్ సృష్టించాలి", hi: "सपोर्ट रिक्वेस्ट बनाएँ" } },
    PERSON,
  ],
  PROVIDER: [
    { id: "readiness", path: "/readiness", label: { en: "Check Paperwork Readiness", te: "పత్రాలు సిద్ధమా చూడాలి", hi: "काग़ज़ात की तैयारी जाँचें" } },
    DOCUMENTS,
    AUTHORIZATION,
    UPLOAD,
    PLAN_BENEFITS,
    PERSON,
  ],
  SUPPORT_AGENT: [
    { id: "queue", path: "/agent", label: { en: "Open Case Queue", te: "కేస్ క్యూ తెరవాలి", hi: "केस क्यू खोलें" } },
    { id: "escalate", message: "When do I escalate a case?", label: { en: "When to Escalate a Case", te: "కేసును ఎప్పుడు ఎస్కలేట్ చేయాలి", hi: "केस कब एस्केलेट करें" } },
    { id: "first", message: "Which cases do I take first?", label: { en: "Which Cases Come First", te: "ముందుగా ఏ కేసులు తీసుకోవాలి", hi: "पहले कौन से केस लें" } },
    PLAN_BENEFITS,
    APPEALS,
  ],
  ADMIN: [
    { id: "dashboard", path: "/admin", label: { en: "Open Admin Dashboard", te: "అడ్మిన్ డాష్‌బోర్డ్ తెరవాలి", hi: "एडमिन डैशबोर्ड खोलें" } },
    { id: "users", path: "/users", label: { en: "Manage Users", te: "వినియోగదారులను నిర్వహించాలి", hi: "उपयोगकर्ता प्रबंधित करें" } },
    PLAN_BENEFITS,
    APPEALS,
  ],
};

export interface ChatText {
  title: string; description: string; newConversation: string; conversation: string; you: string; assistant: string;
  typing: string; placeholder: string; send: string; composerHelp: string; clearTitle: string; clearConfirm: string;
  clearBody: string; copy: string; copied: string; answerTools: string; toolFailed: string; partlyEnglish: string;
  languageLabel: string;
}

export const CHAT_TEXT: Record<Language, ChatText> = {
  en: {
    title: "Assistant", description: "Your first stop for help with your plan, claims, documents and support. Answers come from synthetic prototype data and show their sources.",
    newConversation: "New conversation", conversation: "Conversation", you: "You", assistant: "Assistant", typing: "The assistant is working on your answer…",
    placeholder: "Type your question…", send: "Send", composerHelp: "Enter to send · Shift+Enter for a new line",
    clearTitle: "Start a new conversation?", clearConfirm: "Start new", clearBody: "The current conversation is cleared from this screen. It stays available under Recent conversations.",
    copy: "Copy", copied: "Copied", answerTools: "Answer options", toolFailed: "That didn't work. Please try again.",
    partlyEnglish: "Part of this answer is still in English because a translation service isn't available.", languageLabel: "Language",
  },
  te: {
    title: "అసిస్టెంట్", description: "మీ ప్లాన్, క్లెయిమ్‌లు, డాక్యుమెంట్లు, సపోర్ట్ విషయంలో సహాయం ఇక్కడ పొందండి. సమాధానాలు సింథటిక్ ప్రోటోటైప్ డేటా నుండి వస్తాయి.",
    newConversation: "కొత్త సంభాషణ", conversation: "సంభాషణ", you: "మీరు", assistant: "అసిస్టెంట్", typing: "మీ సమాధానం సిద్ధమవుతోంది…",
    placeholder: "మీ ప్రశ్న టైప్ చేయండి…", send: "పంపండి", composerHelp: "పంపడానికి Enter · కొత్త లైన్‌కు Shift+Enter",
    clearTitle: "కొత్త సంభాషణ మొదలుపెట్టాలా?", clearConfirm: "మొదలుపెట్టండి", clearBody: "ప్రస్తుత సంభాషణ ఈ స్క్రీన్ నుండి తొలగించబడుతుంది. ఇది Recent conversations లో అందుబాటులో ఉంటుంది.",
    copy: "కాపీ", copied: "కాపీ అయింది", answerTools: "సమాధాన ఎంపికలు", toolFailed: "అది పని చేయలేదు. దయచేసి మళ్లీ ప్రయత్నించండి.",
    partlyEnglish: "అనువాద సేవ అందుబాటులో లేనందున ఈ సమాధానంలో కొంత భాగం ఇంగ్లీష్‌లోనే ఉంది.", languageLabel: "భాష",
  },
  hi: {
    title: "असिस्टेंट", description: "अपने प्लान, क्लेम, दस्तावेज़ और सपोर्ट के लिए यहाँ मदद लें। जवाब सिंथेटिक प्रोटोटाइप डेटा से आते हैं।",
    newConversation: "नई बातचीत", conversation: "बातचीत", you: "आप", assistant: "असिस्टेंट", typing: "आपका जवाब तैयार हो रहा है…",
    placeholder: "अपना सवाल लिखें…", send: "भेजें", composerHelp: "भेजने के लिए Enter · नई लाइन के लिए Shift+Enter",
    clearTitle: "नई बातचीत शुरू करें?", clearConfirm: "शुरू करें", clearBody: "मौजूदा बातचीत इस स्क्रीन से हट जाएगी। यह Recent conversations में उपलब्ध रहेगी।",
    copy: "कॉपी", copied: "कॉपी हो गया", answerTools: "जवाब के विकल्प", toolFailed: "यह नहीं हो सका। कृपया दोबारा कोशिश करें।",
    partlyEnglish: "अनुवाद सेवा उपलब्ध न होने से इस जवाब का कुछ हिस्सा अंग्रेज़ी में है।", languageLabel: "भाषा",
  },
};
