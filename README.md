# terraform-impact-analyser

> Terraform tells you **WHAT** will change.
> tf-impact tells you **WHAT WILL HAPPEN** after that change.

## The Problem

When you run terraform plan, you see:

\\\
~ aws_instance.app_server
  ~ instance_type = "t3.medium" -> "t3.large"
\\\

Looks harmless. But nobody tells you:
- EC2 must **stop and restart** to change its type
- Your app will be **down for ~4 minutes**
- The **public IP will change** unless you have an Elastic IP
- Every user gets a **502 error** until the instance is back

tf-impact catches this **before you merge.**

## How It Works

\\\
PR opened
   |
GitHub Actions runs terraform plan
   |
terraform show -json produces plan.json
   |
tf-impact reads plan.json
   |
Claude AI analyses what will happen to real users
   |
Risk engine applies deterministic safety rules
   |
Impact report posted as PR comment
\\\

## What You Get on Every PR

\\\
## TF Impact Analysis

> EC2 instance type change will cause ~4 minutes of downtime.

| Metric          | Value                      |
|-----------------|----------------------------|
| Overall Risk    | HIGH                       |
| Confidence      | 94%                        |
| Downtime        | YES - 4 min                |
| Blast Radius    | HIGH                       |
| Rollback        | Yes                        |

Recommendation: Schedule Maintenance Window
Deploy after midnight on a weekday.
\\\

## Project Structure

\\\
.github/workflows/tf-impact.yml  <- GitHub Actions workflow
terraform/                        <- Sample AWS infrastructure
analyser/
  main.py          <- Orchestrator
  plan_parser.py   <- Reads terraform plan JSON
  ai_analyser.py   <- Calls Claude API
  risk_engine.py   <- Deterministic safety rules
  pr_comment.py    <- Posts GitHub PR comment
  prompts.py       <- AI prompt templates
\\\

## Setup

### 1. Add GitHub Secrets

Go to your repo Settings -> Secrets and variables -> Actions

| Secret | Value |
|--------|-------|
| ANTHROPIC_API_KEY | Your Claude API key from console.anthropic.com |
| AWS_ROLE_ARN | IAM Role ARN for OIDC authentication |

### 2. Create AWS S3 bucket for Terraform state

\\\cmd
aws s3 mb s3://tf-impact-demo-state-bucket --region us-east-1

aws dynamodb create-table --table-name tf-impact-state-lock --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region us-east-1
\\\

### 3. Test it

Change instance_type in terraform/variables.tf from t3.medium to t3.large, raise a PR, and watch tf-impact comment with the full impact analysis.

## Tech Stack

- Terraform - infrastructure as code
- GitHub Actions - CI/CD pipeline
- Python 3.11 - analyser tool
- Claude API by Anthropic - AI impact analysis
- AWS - target cloud provider

## Why This Over Existing Tools?

| Tool | What it does | Gap |
|------|-------------|-----|
| Infracost | Cost estimation | No downtime or blast radius |
| tfsec / Checkov | Security scanning | No operational impact |
| Overmind | Blast radius and risk | Paid SaaS, needs AWS access |
| **tf-impact** | **Full operational impact in plain English** | **Free, open source, runs locally** |

---

Built to solve the real gap: Terraform tells you WHAT changes. tf-impact tells you WHAT HAPPENS.
