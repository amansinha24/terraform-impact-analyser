import json
import os
import time
import anthropic
from prompts import build_system_prompt, build_analysis_prompt


class AIAnalyser:

    MODEL      = "claude-sonnet-4-6"
    MAX_TOKENS = 4096

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to GitHub Secrets.")
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyse(self, plan_summary: dict) -> dict:
        print("🤖 Sending plan to Claude API...")
        start = time.time()

        message = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=build_system_prompt(),
            messages=[{
                "role":    "user",
                "content": build_analysis_prompt(plan_summary),
            }],
        )

        elapsed = time.time() - start
        print(f"   Done in {elapsed:.1f}s | Tokens: {message.usage.input_tokens} in, {message.usage.output_tokens} out")

        return self._parse(message.content[0].text)

    def _parse(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("  "):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"Warning: JSON parse error: {e}")
            return {
                "overall_risk":               "UNKNOWN",
                "confidence":                 0,
                "one_line_summary":           "Analysis failed. Manual review required.",
                "will_cause_downtime":        None,
                "estimated_downtime_minutes": None,
                "estimated_apply_minutes":    None,
                "rollback_possible":          None,
                "rollback_notes":             "Manual review required",
                "deployment_recommendation":  "NEEDS_REVIEW",
                "recommended_deploy_window":  "Do not deploy until reviewed",
                "resource_impacts":           [],
                "blast_radius": {
                    "level":             "UNKNOWN",
                    "affected_services": [],
                    "explanation":       f"Parse error: {e}",
                },
                "security_flags":               [],
                "cost_observation":             None,
                "key_risks":                    ["Automated analysis failed"],
                "what_to_verify_before_apply":  ["Manual review required"],
            }
