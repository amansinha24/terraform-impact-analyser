import json


def build_system_prompt() -> str:
    return '''You are a senior AWS infrastructure engineer with 15 years of experience.

Your job is to analyse a Terraform plan and answer ONE question Terraform never answers:
What will actually happen to users and the business AFTER this change is applied?

RULES:
1. Be specific. EC2 will restart for 4 minutes beats there may be impact.
2. Think in chains. EC2 restarts, Target Group health check fails, ALB stops routing, users see 502.
3. Always give a deployment recommendation.
4. Only use resources from the plan. Do not invent resources.
5. Return ONLY valid JSON. No markdown. No text outside the JSON.
6. Confidence 0-100 means how certain you are given the context.'''


def build_analysis_prompt(plan_summary: dict) -> str:
    plan_json = json.dumps(plan_summary, indent=2)

    return f'''Analyse this Terraform plan and return an impact analysis.

TERRAFORM PLAN:
{plan_json}

Return EXACTLY this JSON structure and nothing else:

{{
  "overall_risk": "LOW or MEDIUM or HIGH or CRITICAL",
  "confidence": 0,
  "one_line_summary": "most important thing about this change in one sentence",
  "will_cause_downtime": true,
  "estimated_downtime_minutes": 0,
  "estimated_apply_minutes": 0,
  "rollback_possible": true,
  "rollback_notes": "how to rollback or null",
  "deployment_recommendation": "SAFE_ANYTIME or SCHEDULE_MAINTENANCE or DO_NOT_DEPLOY or NEEDS_REVIEW",
  "recommended_deploy_window": "e.g. After midnight weekdays or Anytime",
  "resource_impacts": [
    {{
      "resource": "resource address e.g. aws_instance.app_server",
      "resource_type": "human readable e.g. EC2 Instance",
      "impact_level": "NONE or LOW or MEDIUM or HIGH or CRITICAL",
      "what_changes": "what specifically changes",
      "what_happens_to_users": "user impact in plain English",
      "stop_restart_required": true,
      "ip_address_changes": true,
      "downstream_impact": "other resources affected"
    }}
  ],
  "blast_radius": {{
    "level": "NONE or LOW or MEDIUM or HIGH",
    "affected_services": ["list of affected services"],
    "explanation": "plain English how does impact cascade"
  }},
  "security_flags": [
    {{
      "severity": "INFO or WARNING or CRITICAL",
      "message": "security concern"
    }}
  ],
  "cost_observation": "cost impact note or null",
  "key_risks": ["risk 1", "risk 2"],
  "what_to_verify_before_apply": ["check 1", "check 2"]
}}'''
