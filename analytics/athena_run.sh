#!/bin/zsh
# Usage: athena_run.sh "SQL"   -- runs a query in ap-south-1 and prints results
export AWS_REGION=ap-south-1
OUT=s3://whichcloud-analytics-616551057703/athena-results/
QID=$(aws athena start-query-execution --query-string "$1" --result-configuration OutputLocation=$OUT --query QueryExecutionId --output text)
while true; do
  S=$(aws athena get-query-execution --query-execution-id $QID --query 'QueryExecution.Status.State' --output text)
  [[ $S == SUCCEEDED || $S == FAILED || $S == CANCELLED ]] && break; sleep 1
done
if [[ $S != SUCCEEDED ]]; then aws athena get-query-execution --query-execution-id $QID --query 'QueryExecution.Status.StateChangeReason' --output text; exit 1; fi
aws athena get-query-results --query-execution-id $QID --output text --query 'ResultSet.Rows[].Data[].VarCharValue' | head -40
