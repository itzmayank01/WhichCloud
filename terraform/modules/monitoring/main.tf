resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-cloudwatch-alerts"

  tags = merge(var.tags, {
    Name        = "${var.environment}-alerts-topic"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.environment}-asg-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Trigger alert when compute ASG CPU utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    AutoScalingGroupName = var.asg_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.environment}-alb-high-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Trigger alert when 5xx HTTP responses exceed 5 in a minute"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "db_cpu" {
  alarm_name          = "${var.environment}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 120
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "RDS PostgreSQL CPU utilization above 85%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }

  tags = var.tags
}
