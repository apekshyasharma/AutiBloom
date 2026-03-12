import json
import re
import uuid
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from accounts.permissions import role_required, clinician_verified_required
from .models import ChatSession, ChatMessage
import logging


# Line-level citation patterns we scrub after the paren/bracket pass.
_LINE_CITATION_PATTERNS = [
    re.compile(r"(?im)^\s*(?:source|reference|references|sources|citations?)\s*:.*$"),
    re.compile(r"(?i)\b(?:according to|based on|as (?:noted|stated|described) in|per)\s+(?:the\s+)?(?:provided\s+)?(?:context|document|documents|pdf|pdfs|source|sources|reference|references)\b[,:]?\s*"),
]
# Bare (unparenthesised) filename mentions — e.g. "See MyDoc.pdf for details".
# Filenames can contain spaces, word chars, hyphens and apostrophes.
_BARE_PDF_MENTION = re.compile(r"[\w][\w \-'’]*?\.pdf\b", re.IGNORECASE)


def _strip_enclosed_pdf_refs(text: str, open_c: str, close_c: str) -> str:
    """
    Walk the string and drop any top-level (...) / [...] group that contains
    '.pdf', correctly tracking nested parens so a citation like
    '(Parent's Perceptions.pdf, Detection of autism (ASD).pdf)' is removed
    whole instead of leaking the outer tail.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == open_c:
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if text[j] == open_c:
                    depth += 1
                elif text[j] == close_c:
                    depth -= 1
                j += 1
            group = text[i:j]
            if '.pdf' in group.lower():
                # Drop the group; also eat a leading space we had just emitted.
                while out and out[-1] in (' ', '\t'):
                    out.pop()
                i = j
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def scrub_citations(text: str) -> str:
    """Remove any PDF / source citations the LLM may have emitted."""
    if not text:
        return text

    # 1. Balanced paren / bracket groups that mention a PDF.
    text = _strip_enclosed_pdf_refs(text, '(', ')')
    text = _strip_enclosed_pdf_refs(text, '[', ']')

    # 2. Bare "Foo Bar.pdf" mentions outside of any grouping.
    text = _BARE_PDF_MENTION.sub('', text)

    # 3. "Source:" lines and "according to the context" phrasing.
    for pat in _LINE_CITATION_PATTERNS:
        text = pat.sub('', text)

    # 4. Clean up whitespace / punctuation left behind.
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)   # " ." → "."
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

logger = logging.getLogger(__name__)

# Combined decorator for chatbot access
def chatbot_access_required(view_func):
    """
    Caregivers and verified clinicians only.
    """
    view_func = clinician_verified_required(view_func)
    view_func = role_required(["CAREGIVER", "CLINICIAN"])(view_func)
    view_func = login_required(view_func)
    return view_func


@chatbot_access_required
def chat_page(request):
    """Optional full-page view for the chat."""
    return render(request, "chatbot/chat_page.html")


@chatbot_access_required
@require_POST
def chat_ask(request):
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        session_id_str = data.get("session_id")

        if not message:
            return JsonResponse({"error": "Message is required."}, status=400)

        # Retrieve or create session
        session_obj = None
        if session_id_str:
            try:
                session_obj = ChatSession.objects.get(session_key=session_id_str, user=request.user)
            except ChatSession.DoesNotExist:
                pass

        if not session_obj:
            session_obj = ChatSession.objects.create(user=request.user)
            session_id_str = str(session_obj.session_key)

        # 1. Save local user message
        ChatMessage.objects.create(
            session=session_obj,
            role=ChatMessage.Role.USER,
            content=message
        )

        rag_url = getattr(settings, "RAG_SERVICE_URL", "http://127.0.0.1:8001")

        # 2. Call FastAPI POST /api/message
        post_url = f"{rag_url}/api/message"
        post_payload = {
            "session_id": session_id_str,
            "message": message,
            "mode": "auto"
        }
        
        post_resp = requests.post(post_url, json=post_payload, timeout=10)
        post_resp.raise_for_status()
        resp_data = post_resp.json()
        
        request_id = resp_data.get("request_id")
        if not request_id:
            return JsonResponse({"error": "Invalid response from RAG service."}, status=502)

        # 3. Stream SSE from FastAPI GET /api/stream
        stream_url = f"{rag_url}/api/stream?session_id={session_id_str}&request_id={request_id}"
        
        # We consume the SSE on the Django (server) side, to keep the frontend simple
        # and to enforce exactly the 60 second timeout mentioned in the plan.
        # But `requests` with stream=True doesn't have an overall streaming timeout natively for sseclient,
        # so we rely on the internal timeouts and standard usage.
        
        stream_resp = requests.get(stream_url, stream=True, timeout=10)
        stream_resp.raise_for_status()
        
        actual_answer = []
        actual_sources = None

        current_event = None
        for line in stream_resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current_event:
                data_str = line.split(":", 1)[1].strip()
                try:
                    ev_data = json.loads(data_str)
                    if current_event == "token":
                        actual_answer.append(ev_data.get("text", ""))
                    elif current_event == "done":
                        actual_sources = ev_data.get("sources")
                        break
                    elif current_event == "error":
                        return JsonResponse({"error": ev_data.get("message", "Error from RAG service")}, status=502)
                except json.JSONDecodeError:
                    pass
                current_event = None

        final_answer = scrub_citations("".join(actual_answer))

        # 4. Save local assistant message (we still persist the raw sources
        #    for the audit trail, but the API response never exposes them).
        ChatMessage.objects.create(
            session=session_obj,
            role=ChatMessage.Role.ASSISTANT,
            content=final_answer,
            sources=actual_sources,
        )

        return JsonResponse({
            "session_id": session_id_str,
            "answer": final_answer,
        })

    except requests.exceptions.Timeout:
        logger.error("Timeout communicating with RAG service")
        return JsonResponse({"error": "The support chatbot is taking too long to reply. Please try again later."}, status=504)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with RAG service: {e}")
        return JsonResponse({"error": "Unable to connect to the support chatbot. Please try again later."}, status=502)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request."}, status=400)
    except Exception as e:
        logger.exception("Unexpected error in chat_ask")
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)
