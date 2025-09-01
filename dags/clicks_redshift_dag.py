from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.bash import BashOperator

AWS_REGION=os.getenv("AWS_REGION")
S3_BUCKET=os.getenv("S3_BUCKET")
RS_HOST=os.getenv("RS_HOST")
RS_DB=os.getenv("RS_DB")
RS_USER=os.getenv("RS_USER")
RS_PWD=os.getenv("RS_PWD")
RS_PORT=os.getenv("RS_PORT","5439")
ROLE_ARN=os.getenv("RS_ROLE_ARN")  # arn:aws:iam::<acct>:role/RedshiftS3Read

# Copy yesterday or last hour partition; here we do daily
partition="{{ ds }}"

copy_sql=f"""
psql "host={RS_HOST} port={RS_PORT} dbname={RS_DB} user={RS_USER} password={RS_PWD} sslmode=require" -v ON_ERROR_STOP=1 -c "
copy raw_clicks
from 's3://{S3_BUCKET}/bronze/clicks/dt={{{{ ds }}}}/'
iam_role '{ROLE_ARN}'
format as parquet
region '{AWS_REGION}';
"
"""

with DAG(
    "clicks_redshift_hourly",
    start_date=datetime(2025,8,1),
    schedule_interval="0 * * * *",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
) as dag:

    copy_to_redshift = BashOperator(
        task_id="copy_to_redshift",
        bash_command=copy_sql
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        cwd="/home/ouyassine/Documents/projects/Retail Clickstream Mini-Lake/clickstream",   
        bash_command="dbt run"
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        cwd="/home/ouyassine/Documents/projects/Retail Clickstream Mini-Lake/clickstream",
        bash_command="dbt test"
    )

    copy_to_redshift >> dbt_run >> dbt_test
