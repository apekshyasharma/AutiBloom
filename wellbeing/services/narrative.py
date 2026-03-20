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

def call_gemma_model(prompt: str, fallback_text: str = "") -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return fallback_text or "Unable to generate AI summary because GEMINI_API_KEY is not set."
        
    client = genai.Client(api_key=api_key)

    last_err = None
    for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]:
        try:
            cfg_kwargs = dict(temperature=0.2, max_output_tokens=1500)
            # Disable Gemini 2.5 "thinking" so the token budget is spent on visible
            # output, not on internal reasoning that truncates the answer.
            if model.startswith("gemini-2.5"):
                try:
                    cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
                except Exception:
                    pass
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            if resp.text:
                return resp.text
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        print(f"[narrative] All Gemini model calls failed; last error: {last_err}")

    return fallback_text or "Unable to generate AI summary at this time."

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

    fallback_text = f"""Subjective: Caregiver reports weekly check-in data for tracking wellbeing. Child's overall caregiver-reported score is {overall} / 4.0. Concern noted in the following domains: {domains_str}.

Objective: Screening tool processed the caregiver answers. Out of 10 items flagged for risk patterns, {risk_count} / 10 were positive for potential developmental risk. Weekly trends show: {trend_data}.

Assessment: Screening support tool analysis indicates focused concern in {domains_str}. These indicators suggest active patterns that benefit from targeted behavioral tracking.

Plan: Caregiver is advised to monitor flagged domains closely. Recommend sharing the generated clinical summary with a pediatrician or speech/occupational therapist. Maintain weekly wellbeing check-ins to monitor trends.

Disclaimer: AutiBloom's insights are a screening support tool designed to identify patterns, not a clinical diagnosis. Always consult a qualified healthcare or developmental professional for medical advice and evaluation."""

    return call_gemma_model(prompt, fallback_text)

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

    fallback_text = f"""Parent Summary:
We appreciate your dedication to tracking your child's developmental journey. This week, the weekly check-in showed an overall wellbeing score of {overall} out of 4.0, with {risk_count} focus areas flagged by the model. The flagged areas of note are: {domains_str}. Rule-based analysis notes: "{friendly_summary}".

We encourage you to observe how your child navigates routines and communication over the coming days. If you notice persistent high-concern patterns or feel overwhelmed, sharing these weekly tracking summaries with your pediatrician, developmental therapist, or school support team can be a great way to start collaborative care planning.

Disclaimer: AutiBloom's insights are a screening support tool designed to identify patterns, not a clinical diagnosis. Always consult a qualified healthcare or developmental professional for medical advice and evaluation."""

    return call_gemma_model(prompt, fallback_text)
