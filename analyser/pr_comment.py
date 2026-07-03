import os
import requests


class PRCommentFormatter:

    RISK_EMOJI = {
        "CRITICAL": "🚨", "HIGH": "🔴",
        "MEDIUM":   "🟡", "LOW":  "🟢",
        "NONE":     "✅", "UNKNOWN": "❓",
    }

    def format(self, ai_analysis, risk_assessment, parsed_plan, plan_summary) -> str:
        risk      = risk_assessment.overall_risk
        re        = self.RISK_EMOJI.get(risk, "❓")
        summary   = plan_summary.get("summary", {})
        one_liner = ai_analysis.get("one_line_summary", "No summary available.")
        blast     = ai_analysis.get("blast_radius", {})
        blast_lvl = blast.get("level", "UNKNOWN")

        L = []

        L += [
            "## 🔍 TF Impact Analysis", "",
            f"> {one_liner}", "",
            "---", "",
            "### 📊 Risk Dashboard", "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| **Overall Risk** | {re} **{risk}** |",
            f"| **Confidence** | {risk_assessment.confidence}% |",
            f"| **Changes** | "
            f"+{summary.get('to_add',0)} add  "
            f"~{summary.get('to_change',0)} change  "
            f"-{summary.get('to_destroy',0)} destroy  "
            f"↺{summary.get('to_replace',0)} replace |",
        ]

        if risk_assessment.will_cause_downtime:
            dm = risk_assessment.estimated_downtime_minutes
            ds = f"~{dm} min" if dm else "Unknown duration"
            L.append(f"| **Downtime** | ⚠️ **YES — {ds}** |")
        else:
            L.append("| **Downtime** | ✅ No downtime expected |")

        am = risk_assessment.estimated_apply_minutes
        if am:
            L.append(f"| **Estimated Apply Time** | ⏱️ ~{am} min |")

        rb = "✅ Yes" if risk_assessment.rollback_possible else "❌ No — irreversible"
        L.append(f"| **Rollback** | {rb} |")
        L.append(f"| **Blast Radius** | {self.RISK_EMOJI.get(blast_lvl,'❓')} {blast_lvl} |")
        L.append("")

        rec = risk_assessment.deployment_recommendation
        win = risk_assessment.recommended_deploy_window
        L += ["---", "", "### 📋 Deployment Recommendation", ""]
        icons = {
            "DO_NOT_DEPLOY":        "🛑 **DO NOT DEPLOY**",
            "SCHEDULE_MAINTENANCE": "🕐 **Schedule Maintenance Window**",
            "SAFE_ANYTIME":         "✅ **Safe to deploy anytime**",
            "NEEDS_REVIEW":         "👁️ **Manual review required**",
        }
        L.append(f"{icons.get(rec, '❓')} — {win}")

        rn = ai_analysis.get("rollback_notes")
        if rn:
            L += ["", f"**Rollback plan:** {rn}"]
        L.append("")

        if risk_assessment.deterministic_flags:
            L += ["---", "", "### ⚡ Automatic Risk Flags", ""]
            for f in risk_assessment.deterministic_flags:
                L.append(f"- {f}")
            L.append("")

        checks = ai_analysis.get("what_to_verify_before_apply", [])
        if checks:
            L += ["---", "", "### ✅ Verify Before Applying", ""]
            for c in checks:
                L.append(f"- [ ] {c}")
            L.append("")

        impacts = ai_analysis.get("resource_impacts", [])
        if impacts:
            L += ["---", "", "<details>",
                  "<summary>📦 Resource-by-Resource Impact (click to expand)</summary>", ""]
            for imp in impacts:
                lvl = imp.get("impact_level", "UNKNOWN")
                L += [
                    f"#### {self.RISK_EMOJI.get(lvl,'❓')} {imp.get('resource','')}",
                    f"*{imp.get('resource_type','')}*", "",
                    f"**What changes:** {imp.get('what_changes','')}","",
                    f"**User impact:** {imp.get('what_happens_to_users','')}",
                ]
                if imp.get("stop_restart_required"):
                    L += ["", "⚠️ **Stop/Restart required** — downtime expected"]
                if imp.get("ip_address_changes"):
                    L += ["", "⚠️ **IP will change** — update DNS records"]
                di = imp.get("downstream_impact", "")
                if di:
                    L += ["", f"**Downstream:** {di}"]
                L.append("")
            L += ["</details>", ""]

        be = blast.get("explanation", "")
        bs = blast.get("affected_services", [])
        if be:
            L += ["---", "", "<details>",
                  "<summary>💥 Blast Radius Detail (click to expand)</summary>",
                  "", be]
            if bs:
                L += ["", "**Affected:**"]
                for s in bs:
                    L.append(f"- {s}")
            L += ["", "</details>", ""]

        kr = ai_analysis.get("key_risks", [])
        if kr:
            L += ["---", "", "### ⚠️ Key Risks", ""]
            for r in kr:
                L.append(f"- {r}")
            L.append("")

        sf = ai_analysis.get("security_flags", [])
        if sf:
            L += ["---", "", "### 🔐 Security", ""]
            for flag in sf:
                sev = flag.get("severity", "INFO")
                em  = "🚨" if sev == "CRITICAL" else "🟡"
                L.append(f"{em} **{sev}**: {flag.get('message','')}")
            L.append("")

        co = ai_analysis.get("cost_observation")
        if co:
            L += ["---", "", "### 💰 Cost Impact", "", co, ""]

        L += [
            "---", "",
            "<sub>🤖 Generated by "
            "[tf-impact](https://github.com/amansinha24/terraform-impact-analyser) — "
            "AI-powered Terraform impact analysis. "
            "Always apply human judgement before deploying.</sub>",
        ]

        return "\n".join(L)

    def post_to_github(self, comment_body: str) -> bool:
        token  = os.environ.get("GITHUB_TOKEN")
        repo   = os.environ.get("GITHUB_REPOSITORY")
        pr_num = os.environ.get("PR_NUMBER")

        if not all([token, repo, pr_num]):
            print("GitHub env vars missing — printing to stdout.")
            print(comment_body)
            return False

        url = f"https://api.github.com/repos/{repo}/issues/{pr_num}/comments"
        resp = requests.post(
            url,
            headers={
                "Authorization":        f"Bearer {token}",
                "Accept":               "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"body": comment_body},
            timeout=30,
        )

        if resp.status_code == 201:
            print(f"Comment posted: {resp.json().get('html_url','')}")
            return True

        print(f"Post failed: {resp.status_code} — {resp.text[:200]}")
        print(comment_body)
        return False
