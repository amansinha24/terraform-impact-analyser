import json
import os
import time
import boto3
from prompts import build_system_prompt, build_analysis_prompt


class AIAnalyser:

    # For ap-south-1 (Mumbai), Haiku 4.5 requires
    # global cross-region inference profile ID
    MODEL_ID   = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    MAX_TOKENS = 4096
    REGION     = "ap-south-1"

    def __init__(self):
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.REGION,
        )

    def analyse(self, plan_summary: dict) -> dict:
        print("Sending plan to Claude Haiku 4.5 via Amazon Bedrock ap-south-1...")
        start = time.time()

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens":        self.MAX_TOKENS,
            "system":            build_system_prompt(),
            "messages": [
                {
                    "role":    "user",
                    "content": build_analysis_prompt(plan_summary),
                }
            ],
        })

        response = self.client.invoke_model(
            modelId=self.MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        elapsed       = time.time() - start
        response_body = json.loads(response["body"].read())
        raw_text      = response_body["content"][0]["text"]
        usage         = response_body.get("usage", {})

        print(f"   Done in {elapsed:.1f}s | "
              f"Tokens: {usage.get('input_tokens', '?')} in, "
              f"{usage.get('output_tokens', '?')} out")

        return self._parse(raw_text)

    def _parse(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("`"):
            lines   = cleaned.split("\n")
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
                "security_flags":              [],
                "cost_observation":            None,
                "key_risks":                   ["Automated analysis failed"],
                "what_to_verify_before_apply": ["Manual review required"],
            }
