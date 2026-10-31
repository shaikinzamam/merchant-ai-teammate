"""Localised reply templates. Hi/En are complete; Te/Kn cover core flows and fall back to English.
NOTE: all non-English strings need review by native speakers before any real use."""
from __future__ import annotations

from app.schemas.domain import Language as L

T: dict[str, dict[L, str]] = {
    "settlement_delayed": {
        L.EN: "Your settlement for {date} is delayed because of bank-holiday clearing. "
              "It is expected to be credited by {expected_by}.",
        L.HI: "आपका {date} का सेटलमेंट बैंक की छुट्टी के कारण थोड़ा देर से है। "
              "यह {expected_by} तक आपके खाते में आ जाएगा।",
        L.TE: "{date} సెటిల్‌మెంట్ బ్యాంక్ సెలవు కారణంగా ఆలస్యమైంది. {expected_by} కల్లా జమ అవుతుంది.",
        L.KN: "{date} ಸೆಟಲ್‌ಮೆಂಟ್ ಬ್ಯಾಂಕ್ ರಜೆಯ ಕಾರಣ ವಿಳಂಬವಾಗಿದೆ. {expected_by} ಒಳಗೆ ಜಮೆಯಾಗುತ್ತದೆ.",
    },
    "settlement_settled": {
        L.EN: "Your settlement for {date} has been completed.",
        L.HI: "आपका {date} का सेटलमेंट पूरा हो चुका है।",
        L.TE: "{date} సెటిల్‌మెంట్ పూర్తయింది.",
        L.KN: "{date} ಸೆಟಲ್‌ಮೆಂಟ್ ಪೂರ್ಣಗೊಂಡಿದೆ.",
    },
    "qr_reissue_done": {
        L.EN: "Your replacement QR request ({request_id}) has been submitted.",
        L.HI: "आपकी नया QR की रिक्वेस्ट ({request_id}) दर्ज कर दी गई है।",
    },
    "soundbox_status": {
        L.EN: "Your Soundbox status: {status}.",
        L.HI: "आपके Soundbox की स्थिति: {status}।",
    },
    "approval_pending": {
        L.EN: "I've prepared this request and sent it to our team for approval. "
              "You'll hear back once it's reviewed.",
        L.HI: "मैंने आपकी रिक्वेस्ट तैयार करके हमारी टीम को अनुमोदन के लिए भेज दी है। "
              "समीक्षा के बाद आपको बताया जाएगा।",
        L.TE: "మీ అభ్యర్థనను సిద్ధం చేసి ఆమోదం కోసం మా బృందానికి పంపాను.",
        L.KN: "ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಸಿದ್ಧಪಡಿಸಿ ಅನುಮೋದನೆಗಾಗಿ ನಮ್ಮ ತಂಡಕ್ಕೆ ಕಳುಹಿಸಲಾಗಿದೆ.",
    },
    "escalated": {
        L.EN: "I've passed your case to a specialist on our team, who will follow up with you.",
        L.HI: "मैंने आपका मामला हमारी टीम के विशेषज्ञ को भेज दिया है, वे आपसे संपर्क करेंगे।",
        L.TE: "మీ కేసును మా నిపుణుడికి పంపాను, వారు మిమ్మల్ని సంప్రదిస్తారు.",
        L.KN: "ನಿಮ್ಮ ಪ್ರಕರಣವನ್ನು ನಮ್ಮ ತಜ್ಞರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ, ಅವರು ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ.",
    },
    "denied": {
        L.EN: "I'm not able to do that automatically. A team member can help you with it.",
        L.HI: "मैं यह अपने आप नहीं कर सकता। हमारी टीम का सदस्य आपकी मदद कर सकता है।",
    },
    "tool_failed": {
        L.EN: "Something went wrong on our side. Please try again in a little while.",
        L.HI: "हमारी तरफ से कुछ गड़बड़ हुई। कृपया थोड़ी देर बाद फिर कोशिश करें।",
    },
    "need_txn_id": {
        L.EN: "Please share the transaction ID (it starts with TXN) so I can raise the dispute.",
        L.HI: "कृपया ट्रांज़ैक्शन ID (TXN से शुरू होती है) बताइए ताकि मैं डिस्प्यूट दर्ज कर सकूँ।",
    },
    "unknown_intent": {
        L.EN: "I couldn't quite understand that. Could you tell me a bit more about the problem?",
        L.HI: "मैं समझ नहीं पाया। क्या आप समस्या थोड़ा और बता सकते हैं?",
    },
    "voice_empty": {
        L.EN: "I couldn't hear that. Please try again or type your message.",
        L.HI: "मैं सुन नहीं पाया। कृपया फिर से बोलें या अपना संदेश टाइप करें।",
        L.TE: "మీ మాటలు వినిపించలేదు. దయచేసి మళ్లీ ప్రయత్నించండి లేదా టైప్ చేయండి.",
        L.KN: "ನಿಮ್ಮ ಮಾತು ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ ಟೈಪ್ ಮಾಡಿ.",
    },
    "growth_hint": {
        L.EN: "Also, based on your sales volume, our team may be able to tell you about {product}.",
        L.HI: "आपकी बिक्री को देखते हुए, हमारी टीम आपको {product} के बारे में बता सकती है।",
    },
}
