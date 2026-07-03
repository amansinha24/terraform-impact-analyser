import json
import os
import time
import boto3
from prompts import build_system_prompt, build_analysis_prompt


class AIAnalyser:

    # Claude Haiku 3.5 on Amazon Bedrock
    # Free tier available, fast, and cost-effective
    MODEL_ID   = "us.anthropic.claude-haiku-3-5-20241022-v1:0"
    MAX_TOKENS = 4096
    REGION     = "us-east-1"

    def __init__(self):
        # Bedrock uses AWS credentials — same OIDC role
        # already configured in GitHub Actions workflow.
        # No separate API key needed.
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.REGION,
        )

    def analyse(self, plan_summary: dict) -> dict:
        print("🤖 Sending plan to Claude Haiku 3.5 via Amazon Bedrock...")
        start = time.time()

        # Bedrock uses the Messages API format
        # Same structure as Anthropic SDK but called via boto3
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

        elapsed = time.time() - start

        # Parse the response body
        response_body = json.loads(response["body"].read())
        raw_text      = response_body["content"][0]["text"]

        usage = response_body.get("usage", {})
        print(f"   Done in {elapsed:.1f}s | "
              f"Tokens: {usage.get('input_tokens', '?')} in, "
              f"{usage.get('output_tokens', '?')} out")

        return self._parse(raw_text)

    def _parse(self, raw: str) -> dict:
        cleaned = raw.strip()

        # Remove markdown code fences if model added them
        if cleaned.startswith("  "):
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
