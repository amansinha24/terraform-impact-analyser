import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AttributeChange:
    attribute:      str
    before:         Optional[str]
    after:          Optional[str]
    forces_replace: bool = False


@dataclass
class ResourceChange:
    address:           str
    resource_type:     str
    name:              str
    action:            str
    module:            Optional[str]
    attribute_changes: list = field(default_factory=list)
    forces_replace:    bool = False


@dataclass
class ParsedPlan:
    total_add:               int
    total_change:            int
    total_destroy:           int
    total_replace:           int
    resource_changes:        list = field(default_factory=list)
    has_destructive_changes: bool = False
    terraform_version:       str  = ""


class TerraformPlanParser:

    EC2_STOP_START_ATTRIBUTES = {
        "instance_type", "ami", "user_data",
        "subnet_id", "key_name", "iam_instance_profile",
    }

    RESOURCE_LABELS = {
        "aws_instance":            "EC2 Instance",
        "aws_lb":                  "Application Load Balancer",
        "aws_lb_target_group":     "Load Balancer Target Group",
        "aws_lb_listener":         "Load Balancer Listener",
        "aws_lb_target_group_attachment": "Target Group Attachment",
        "aws_db_instance":         "RDS Database",
        "aws_db_subnet_group":     "RDS Subnet Group",
        "aws_security_group":      "Security Group",
        "aws_autoscaling_group":   "Auto Scaling Group",
        "aws_launch_template":     "Launch Template",
        "aws_s3_bucket":           "S3 Bucket",
        "aws_iam_role":            "IAM Role",
        "aws_iam_policy":          "IAM Policy",
        "aws_cloudwatch_alarm":    "CloudWatch Alarm",
        "aws_vpc":                 "VPC",
        "aws_subnet":              "Subnet",
        "aws_eks_cluster":         "EKS Kubernetes Cluster",
        "aws_eks_node_group":      "EKS Node Group",
        "aws_lambda_function":     "Lambda Function",
        "aws_api_gateway_rest_api": "API Gateway",
    }

    def __init__(self, plan_json_path: str):
        self.plan_json_path = plan_json_path

    def parse(self) -> ParsedPlan:
        with open(self.plan_json_path) as f:
            raw = json.load(f)

        tf_version  = raw.get("terraform_version", "unknown")
        changes_raw = raw.get("resource_changes", [])

        resource_changes = []
        add = change = destroy = replace = 0
        has_destructive = False

        for item in changes_raw:
            rc = self._parse_resource(item)
            if rc is None:
                continue
            if rc.action == "create":
                add += 1
            elif rc.action == "update":
                change += 1
            elif rc.action == "delete":
                destroy += 1
                has_destructive = True
            elif rc.action == "replace":
                replace += 1
                has_destructive = True
            resource_changes.append(rc)

        return ParsedPlan(
            total_add=add,
            total_change=change,
            total_destroy=destroy,
            total_replace=replace,
            resource_changes=resource_changes,
            has_destructive_changes=has_destructive,
            terraform_version=tf_version,
        )

    def _parse_resource(self, item: dict) -> Optional[ResourceChange]:
        change_data = item.get("change", {})
        actions     = change_data.get("actions", ["no-op"])

        if actions == ["no-op"]:
            return None

        if "delete" in actions and "create" in actions:
            action = "replace"
        elif "delete" in actions:
            action = "delete"
        elif "create" in actions:
            action = "create"
        elif "update" in actions:
            action = "update"
        else:
            action = "unknown"

        rtype   = item.get("type",    "")
        rname   = item.get("name",    "")
        address = item.get("address", "")
        module  = item.get("module_address")

        attr_changes = self._get_attr_changes(change_data, rtype)
        forces = action == "replace" or any(a.forces_replace for a in attr_changes)

        return ResourceChange(
            address=address, resource_type=rtype, name=rname,
            action=action, module=module,
            attribute_changes=attr_changes, forces_replace=forces,
        )

    def _get_attr_changes(self, change_data: dict, rtype: str) -> list:
        before = change_data.get("before") or {}
        after  = change_data.get("after")  or {}

        replace_paths = set()
        for path_list in change_data.get("replace_paths", []):
            if path_list:
                replace_paths.add(str(path_list[0]))

        result = []
        for key in set(before) | set(after):
            bv = before.get(key)
            av = after.get(key)
            if bv == av:
                continue
            if key in ("id", "arn", "tags_all"):
                continue
            forces = key in replace_paths
            if rtype == "aws_instance" and key in self.EC2_STOP_START_ATTRIBUTES:
                forces = True
            result.append(AttributeChange(
                attribute=key,
                before=str(bv) if bv is not None else None,
                after=str(av)  if av  is not None else None,
                forces_replace=forces,
            ))
        return result

    def to_summary_dict(self, parsed: ParsedPlan) -> dict:
        changes = []
        for rc in parsed.resource_changes:
            label = self.RESOURCE_LABELS.get(rc.resource_type, rc.resource_type)
            attrs = [
                {
                    "attribute":      a.attribute,
                    "before":         a.before,
                    "after":          a.after,
                    "forces_replace": a.forces_replace,
                }
                for a in rc.attribute_changes
            ]
            changes.append({
                "address":           rc.address,
                "resource_type":     rc.resource_type,
                "human_description": label,
                "action":            rc.action,
                "module":            rc.module,
                "forces_replace":    rc.forces_replace,
                "attribute_changes": attrs,
            })

        return {
            "summary": {
                "to_add":                  parsed.total_add,
                "to_change":               parsed.total_change,
                "to_destroy":              parsed.total_destroy,
                "to_replace":              parsed.total_replace,
                "has_destructive_changes": parsed.has_destructive_changes,
                "terraform_version":       parsed.terraform_version,
            },
            "resource_changes": changes,
        }
