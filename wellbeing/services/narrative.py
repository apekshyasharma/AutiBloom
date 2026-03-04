import os
import json
from google import genai
from google.genai import types

DOMAIN_LABELS = {
    "communication": "Communication",
    "routines": "Routines",
    "emotional_responses": "Emotional Responses",
    "sensory_behaviors": "Sensory Behaviors",
}

def call_gemma_model(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Unable to generate AI summary because GEMINI_API_KEY is not set."
        
    client = genai.Client(api_key=api_key)
    model = "gemma-3-27b-it"
    
    try:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=800
            ),
        )
        return resp.text
    except Exception as e:
        return f"Unable to generate AI summary at this time: {str(e)}"

def build_soap_note(trend_summary: dict, prediction) -> str:
    """Build an AI-powered SOAP medical note using Gemma-3-27B-IT."""
    exp = prediction.explanation_json or {}
    
    risk_count = exp.get("risk_count", 0)
    top_domains = exp.get("top_domains", [])
    
    trends = trend_summary.get("domain_trends", {})
    latest_overall = trend_summary.get("latest_overall")
    
    trend_data = json.dumps(trends, indent=2)
    overall = f"{latest_overall:.1f}" if latest_overall else "N/A"
    domains_str = ", ".join([DOMAIN_LABELS.get(d, d) for d in top_domains]) if top_domains else "None"
    
    prompt = f"""You are a professional medical scribe summarizing caregiver-reported tracking data for an autistic child.
Write a strict SOAP (Subjective, Objective, Assessment, Plan) note based on the caregiver's weekly check-in data and model insights.

STRICT RULES:
1. ONLY output the SOAP note (4 sections clearly labeled: Subjective:, Objective:, Assessment:, Plan:).
2. DO NOT include any introductory or concluding conversational text.
3. Be clinical, objective, and concise. No conversational fluff.
4. Note that the data is caregiver-reported via a screening support tool.

CONTEXT DATA:
- Overall Caregiver-Reported Wellbeing Score: {overall} / 4.0
- Number of Flagged Items: {risk_count} / 10
- Highest Concern Domains: {domains_str}
- Domain Trends (up=improvement, down=worsening, stable):
{trend_data}

Write the SOAP note now:"""
    return call_gemma_model(prompt)

def build_narrative(trend_summary: dict, prediction) -> str:
    """Build an AI-powered narrative summary using Gemma-3-27B-IT."""
    exp = prediction.explanation_json or {}
    risk_count = exp.get("risk_count", 0)
    top_domains = exp.get("top_domains", [])
    friendly_summary = exp.get("friendly_summary", "")
    trends = trend_summary.get("domain_trends", {})
    latest_overall = trend_summary.get("latest_overall")
    
    trend_data = json.dumps(trends, indent=2)
    overall = f"{latest_overall:.1f}" if latest_overall else "N/A"
    domains_str = ", ".join([DOMAIN_LABELS.get(d, d) for d in top_domains]) if top_domains else "None"

    prompt = f"""You are a compassionate, professional support assistant for parents of autistic children.
Your task is to write a short "Parent Summary" narrative based on the provided weekly tracking data and machine-learning model insights.

STRICT RULES:
1. DO NOT make any clinical diagnoses.
2. DO NOT give specific medical advice.
3. BE ENCOURAGING and supportive.
4. Format the output with exactly two or three short paragraphs.
5. Emphasize that these insights are based on a support tool, not a medical evaluation.
6. If the risk level is high (over 4 flagged items), suggest sharing the observations with a pediatrician or therapist.
7. Use the weekly trends to contextualize the summary.

CONTEXT DATA:
- Overall Wellbeing Score: {overall} out of 4.0
- Number of Flagged Risk Patterns: {risk_count}
- Focus Domains Flagged by Model: {domains_str}
- Rule-based Short Summary: "{friendly_summary}"
- Weekly Domain Trends (up=improvement, down=needs support, stable=no change):
{trend_data}

Based strictly on the rules and data above, write the parent summary narrative now. 
Disclaimer: AutiBloom's insights are a screening support tool designed to identify patterns, not a clinical diagnosis. Always consult a qualified healthcare or developmental professional for medical advice and evaluation. Add this at the end of the text.
"""
    return call_gemma_model(prompt)
