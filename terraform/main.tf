data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

locals {
  env = var.environment == "" ? "dev" : var.environment
  common_tags = {
    Environment = local.env
    Project     = "tf-impact-demo"
    ManagedBy   = "Terraform"
  }
}

resource "aws_security_group" "alb_sg" {
  name        = "tfimpact-${local.env}-alb-sg"
  description = "Allow HTTP to ALB"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.common_tags
}

resource "aws_security_group" "ec2_sg" {
  name        = "tfimpact-${local.env}-ec2-sg"
  description = "Allow traffic from ALB only"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.common_tags
}

resource "aws_security_group" "rds_sg" {
  name        = "tfimpact-${local.env}-rds-sg"
  description = "Allow MySQL from EC2 only"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }
  tags = local.common_tags
}

resource "aws_instance" "app_server" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]
  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
    tags        = local.common_tags
  }
  tags = merge(local.common_tags, { Name = "tfimpact-${local.env}-app-server" })
  lifecycle {
    create_before_destroy = false
  }
}

resource "aws_lb" "app_alb" {
  name               = "tfimpact-${local.env}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = data.aws_subnets.default.ids
  enable_deletion_protection = false
  tags = local.common_tags
}

resource "aws_lb_target_group" "app_tg" {
  name     = "tfimpact-${local.env}-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id
  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
  tags = local.common_tags
}

resource "aws_lb_target_group_attachment" "app" {
  target_group_arn = aws_lb_target_group.app_tg.arn
  target_id        = aws_instance.app_server.id
  port             = 8080
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app_alb.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_tg.arn
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "tfimpact-${local.env}-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
  tags       = local.common_tags
}

resource "aws_db_instance" "app_db" {
  identifier             = "tfimpact-${local.env}-db"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_storage_gb
  db_name                = "appdb"
  username               = "admin"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  storage_encrypted       = true
  tags                    = local.common_tags
}