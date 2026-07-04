from dataclasses import dataclass, field


@dataclass
class RiskAssessment:
    overall_risk:               str
    risk_score:                 int
    confidence:                 int
    will_cause_downtime:        bool
    estimated_downtime_minutes: object
    estimated_apply_minutes:    object
    rollback_possible:          bool
    deployment_recommendation:  str
    recommended_deploy_window:  str
    deterministic_flags:        list = field(default_factory=list)


class RiskEngine:

    RISK_ORDER  = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    RISK_SCORES = {"NONE": 0, "LOW": 25, "MEDIUM": 50, "HIGH": 75, "CRITICAL": 95}

    def assess(self, parsed_plan, ai_analysis: dict) -> RiskAssessment:
        flags = []

        for rc in parsed_plan.resource_changes:

            if rc.resource_type in {"aws_db_instance", "aws_db_cluster"} \
                    and rc.action in {"delete", "replace"}:
                flags.append(
                    "CRITICAL: Database is being DELETED or REPLACED. "
                    "Risk of permanent data loss. Requires DBA sign-off."
                )

            if rc.resource_type == "aws_lb" and rc.action in {"delete", "replace"}:
                flags.append(
                    "HIGH: Load Balancer is being replaced. "
                    "ALL traffic will be lost during recreation."
                )

            if rc.resource_type == "aws_vpc" and rc.action != "create":
                flags.append(
                    "CRITICAL: VPC is being modified. "
                    "This affects ALL resources in the network."
                )

            if rc.resource_type == "aws_security_group" and rc.action == "delete":
                flags.append(
                    "WARNING: Security Group deleted. "
                    "Resources using it will immediately lose network access."
                )

            if rc.resource_type == "aws_iam_role" and rc.action == "delete":
                flags.append(
                    "WARNING: IAM Role deleted. "
                    "Lambda or EC2 using this role will lose permissions immediately."
                )

            if rc.resource_type == "aws_instance":
                for attr in rc.attribute_changes:
                    if attr.attribute == "instance_type" and attr.before is not None:
                        flags.append(
                            f"WARNING: EC2 instance_type changing "
                            f"{attr.before} to {attr.after}. "
                            f"AWS requires STOP then START. "
                            f"Public IP will change unless Elastic IP is used."
                        )

        ai_risk    = ai_analysis.get("overall_risk", "MEDIUM")
        final_risk = ai_risk

        if any("CRITICAL" in f for f in flags):
            final_risk = self._max_risk(final_risk, "CRITICAL")
        elif any("HIGH" in f for f in flags):
            final_risk = self._max_risk(final_risk, "HIGH")

        if parsed_plan.has_destructive_changes and final_risk == "LOW":
            final_risk = "MEDIUM"
            flags.append("Risk raised to MEDIUM: plan has destructive changes.")

        return RiskAssessment(
            overall_risk=final_risk,
            risk_score=self.RISK_SCORES.get(final_risk, 50),
            confidence=ai_analysis.get("confidence", 80),
            will_cause_downtime=ai_analysis.get("will_cause_downtime", False),
            estimated_downtime_minutes=ai_analysis.get("estimated_downtime_minutes"),
            estimated_apply_minutes=ai_analysis.get("estimated_apply_minutes"),
            rollback_possible=ai_analysis.get("rollback_possible", True),
            deployment_recommendation=ai_analysis.get("deployment_recommendation", "NEEDS_REVIEW"),
            recommended_deploy_window=ai_analysis.get("recommended_deploy_window", "Review before deploying"),
            deterministic_flags=flags,
        )

    def _max_risk(self, current: str, challenger: str) -> str:
        ci = self.RISK_ORDER.index(current)    if current    in self.RISK_ORDER else 2
        xi = self.RISK_ORDER.index(challenger) if challenger in self.RISK_ORDER else 2
        return self.RISK_ORDER[max(ci, xi)]
