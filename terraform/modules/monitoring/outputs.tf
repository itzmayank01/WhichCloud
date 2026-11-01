output "sns_topic_arn" {
  description = "ARN of the CloudWatch alarms SNS topic"
  value       = aws_sns_topic.alerts.arn
}

output "high_cpu_alarm_id" {
  description = "CloudWatch High CPU Alarm ID"
  value       = aws_cloudwatch_metric_alarm.high_cpu.id
}
