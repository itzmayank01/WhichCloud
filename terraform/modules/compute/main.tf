# Application Load Balancer Security Group
resource "aws_security_group" "alb" {
  name        = "${var.environment}-alb-sg"
  description = "Allow inbound HTTP/HTTPS traffic to ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from Internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from Internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-alb-sg"
    Environment = var.environment
  })
}

# Compute Instances Security Group
resource "aws_security_group" "app" {
  name        = "${var.environment}-app-sg"
  description = "Allow ingress strictly from ALB"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Traffic from ALB"
    from_port       = 8010
    to_port         = 8010
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-app-sg"
    Environment = var.environment
  })
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.environment == "prod" ? true : false

  tags = merge(var.tags, {
    Name        = "${var.environment}-alb"
    Environment = var.environment
  })
}

resource "aws_lb_target_group" "app" {
  name        = "${var.environment}-tg"
  port        = 8010
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/health"
    port                = "8010"
    protocol            = "HTTP"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15
    matcher             = "200"
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-tg"
    Environment = var.environment
  })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Launch Template for Compute Auto Scaling
resource "aws_launch_template" "app" {
  name_prefix   = "${var.environment}-app-lt-"
  image_id      = "ami-0c55b159cbfafe1f0" # Amazon Linux 2023 ARM64
  instance_type = var.instance_type

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.app.id]
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              echo "Starting WhichCloud service in ${var.environment}..."
              yum update -y
              EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name        = "${var.environment}-app-node"
      Environment = var.environment
    })
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "app" {
  name_prefix         = "${var.environment}-asg-"
  vpc_zone_identifier = var.private_subnet_ids
  target_group_arns   = [aws_lb_target_group.app.arn]

  min_size         = var.min_capacity
  max_size         = var.max_capacity
  desired_capacity = var.desired_capacity

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  health_check_type         = "ELB"
  health_check_grace_period = 300

  tag {
    key                 = "Name"
    value               = "${var.environment}-app-instance"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Dynamic Scaling Policy
resource "aws_autoscaling_policy" "cpu_target" {
  name                   = "${var.environment}-cpu-target-scaling"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.target_cpu_utilization
  }
}
