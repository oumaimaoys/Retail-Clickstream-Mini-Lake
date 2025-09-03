from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.bash import BashOperator
from dotenv import load_dotenv
from pathlib import Path

from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig
from cosmos.profiles import RedshiftUserPasswordProfileMapping

# Load .env file at project root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
RS_HOST = os.getenv("RS_HOST")
RS_DB = os.getenv("RS_DB")
RS_USER = os.getenv("RS_USER")
RS_PWD = os.getenv("RS_PWD")
RS_PORT = os.getenv("RS_PORT", "5439")
ROLE_ARN = os.getenv("RS_ROLE_ARN")

# SQL for COPY command
copy_sql = f"""
psql "host={RS_HOST} port={RS_PORT} dbname={RS_DB} user={RS_USER} password={RS_PWD} sslmode=require" -v ON_ERROR_STOP=1 -c "
copy staging_raw.raw_clicks
from 's3://{S3_BUCKET}/bronze/clicks/dt={{{{ ds }}}}/'
iam_role '{ROLE_ARN}'
format as parquet
region '{AWS_REGION}';
"
"""

# Redshift profile config for dbt
profile_config = ProfileConfig(
    profile_name="default",
    target_name="dev",
    profile_mapping=RedshiftUserPasswordProfileMapping(
        conn_id="redshift_conn",  # <-- must exist in Airflow Connections
        profile_args={"dbname": RS_DB, "schema": "staging_raw"},
    ),
)

# Define main DAG
with DAG(
    "clicks_redshift_hourly",
    start_date=datetime(2025, 8, 1),
    schedule="0 * * * *",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
) as dag:

    copy_to_redshift = BashOperator(
        task_id="copy_to_redshift",
        bash_command=copy_sql,
    )

    # dbt task group (instead of sub-DAG)
    dbt_tg = DbtTaskGroup(
        group_id="dbt_run",
        project_config=ProjectConfig("/usr/local/airflow/dags/clickstream"),
        profile_config=profile_config,
        execution_config=ExecutionConfig(dbt_executable_path="dbt"),
        operator_args={"install_deps": True},
    )

    # Wire tasks
    copy_to_redshift >> dbt_tg
