BASE=/home/ouyassine/spark-jars

CP="$BASE/spark-sql-kafka-0-10_2.13-4.0.0.jar:$BASE/spark-token-provider-kafka-0-10_2.13-4.0.0.jar:$BASE/kafka-clients-3.7.0.jar:$BASE/lz4-java-1.8.0.jar:$BASE/snappy-java-1.1.10.5.jar:$BASE/hadoop-aws-3.3.6.jar:$BASE/aws-java-sdk-bundle-1.12.367.jar:$BASE/commons-pool2-2.12.0.jar"

JARS="$BASE/spark-sql-kafka-0-10_2.13-4.0.0.jar,$BASE/spark-token-provider-kafka-0-10_2.13-4.0.0.jar,$BASE/kafka-clients-3.7.0.jar,$BASE/lz4-java-1.8.0.jar,$BASE/snappy-java-1.1.10.5.jar,$BASE/hadoop-aws-3.3.6.jar,$BASE/aws-java-sdk-bundle-1.12.367.jar,$BASE/commons-pool2-2.12.0.jar"

spark-submit \
  --master local[2] \
  --jars "$JARS" \
  --driver-class-path "$CP" \
  --conf "spark.executor.extraClassPath=$CP" \
  --conf "spark.driver.userClassPathFirst=true" \
  --conf "spark.executor.userClassPathFirst=true" \
  --conf "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem" \
  src/stream_to_s3.py


# Retail Clickstream Mini-Lake (Kafka → Spark → S3 → Redshift → dbt → Superset)

A small, production-style **streaming ELT** project that simulates website clickstream data, lands it to an S3 data lake (bronze), loads it into **Amazon Redshift**, models analytics marts with **dbt**, and visualizes KPIs in **Apache Superset**.

> Pattern: **Kafka (events) → Spark Structured Streaming (ingest) → S3 (Parquet) → Redshift (COPY) → dbt (models + tests) → Superset (dashboard)**

---

## 🚀 Highlights
- **Streaming ingestion**: Python generator ➜ Kafka topic `clicks`
- **Data lake bronze**: PySpark Structured Streaming ➜ S3 Parquet (date-partitioned)
- **Warehouse**: Redshift `COPY` from S3 into `raw.raw_clicks`
- **Transforms**: dbt staging + marts (`stg_clicks`, `fct_sessions`) with tests & docs
- **BI**: Superset dashboard (sessions, conversion, top pages/devices, funnel)
- **Ops**: Airflow DAG for hourly load & dbt; optional Terraform for S3/IAM/Redshift

---

## 🧱 Architecture

```
[Python generator]
        │
        ▼
     Kafka (topic: clicks)
        │  (Structured Streaming)
        ▼
  Spark → S3 (Parquet, /bronze/clicks/dt=YYYY-MM-DD)
        │                     │              \ (COPY)
        ▼                    Redshift  <---------  S3
        │
        │  dbt (models + tests)
        ▼
  stg_clicks (view/table) ──► fct_sessions (table)
        │
        ▼
    Superset dashboard
```

---

## 🧰 Tech Stack

- **Data Gen & Streaming**: Python, `kafka-python`, Apache Kafka (Docker)
- **Ingest**: PySpark 3.5 (Structured Streaming), Parquet
- **Storage**: Amazon S3 (bronze)
- **Warehouse**: Amazon Redshift (provisioned or serverless)
- **Modeling**: dbt-redshift (sources, models, tests, docs)
- **Orchestration**: Apache Airflow (hourly `COPY` + dbt run/test)
- **Viz**: Apache Superset
- **Infra (optional)**: Terraform (S3 bucket, IAM role, Redshift)

---

## 📁 Project Structure

```
.
├─ docker/                  # docker-compose for kafka, ui, (optional) airflow/spark
├─ producers/
│   └─ clickstream_producer.py
├─ spark/
│   └─ stream_to_s3.py      # Kafka -> S3 (bronze)
├─ dbt/
│   └─ clickstream/
│       ├─ models/
│       │   ├─ _sources.yml
│       │   ├─ stg_clicks.sql
│       │   ├─ fct_sessions.sql
│       │   └─ schema.yml    # tests
│       └─ profiles.yml      # or use ~/.dbt/profiles.yml
├─ airflow_home/
│   └─ dags/
│       └─ clicks_redshift_dag.py
├─ superset/                # (optional) saved charts/export JSON
├─ terraform/               # (optional) S3/IAM/Redshift
├─ .env                     # ⚠️ NOT committed; secrets & config
└─ README.md
```

---

## 🔐 Configuration

Create a **`.env`** at the repo root (do **not** commit it):

```env
# AWS
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=rcml-clicks-yourname

# Kafka
KAFKA_BOOTSTRAP=localhost:9092

# Redshift
RS_HOST=your-redshift-endpoint.region.redshift.amazonaws.com
RS_DB=dev
RS_USER=awsuser
RS_PWD=SuperSecret123
RS_PORT=5439
RS_ROLE_ARN=arn:aws:iam::<acct>:role/RedshiftS3Read
```

> Tip: keep a committed `.env.example` without secrets to document required keys.

---

## ✅ Prerequisites

- AWS account + S3 bucket + Redshift (serverless or cluster)
- IAM role for Redshift with S3 read access (attach `AmazonS3ReadOnlyAccess` or least-privilege)
- Python 3.10+, Java 11+, Docker, docker-compose, AWS CLI
- dbt-redshift, Airflow, Superset (local or Docker)

---

## 1) Start Kafka Locally

```bash
docker compose -f docker/docker-compose.kafka.yml up -d
# create topic 'clicks' if compose doesn't
docker exec -it $(docker ps -qf name=kafka)   kafka-topics --bootstrap-server localhost:9092 --create --topic clicks --partitions 3 --replication-factor 1
```

---

## 2) Run the Clickstream Generator

```bash
pip install -r producers/requirements.txt  # kafka-python, python-dotenv, faker (optional)
python producers/clickstream_producer.py   # reads .env automatically
```

Emitted fields: `event_id, customer_id, session_id, event_type, page, utm_campaign, device, geo_city, event_ts, source`.

---

## 3) Stream to S3 (Bronze)

```bash
pip install pyspark==3.5.1 python-dotenv
# Add hadoop-aws & aws-java-sdk-bundle jars to SPARK_HOME/jars if needed
python spark/stream_to_s3.py
```

Output: `s3://$S3_BUCKET/bronze/clicks/dt=YYYY-MM-DD/part-*.parquet`  
Check with AWS Console or `aws s3 ls s3://$S3_BUCKET/bronze/clicks/ --recursive`.

---

## 4) Load to Redshift (COPY)

Create schema/table (Query Editor v2):

```sql
create schema if not exists raw;

create table if not exists raw.raw_clicks (
  event_id varchar(64),
  customer_id varchar(64),
  session_id varchar(64),
  event_type varchar(32),
  page varchar(256),
  utm_campaign varchar(64),
  device varchar(16),
  geo_city varchar(64),
  event_ts timestamp,
  source varchar(32),
  dt date
);
```

Copy a partition (adjust bucket, date, region, role ARN):

```sql
copy raw.raw_clicks
from 's3://rcml-clicks-yourname/bronze/clicks/dt=2025-08-24/'
iam_role 'arn:aws:iam::<acct>:role/RedshiftS3Read'
format as parquet
region 'eu-west-1';
```

---

## 5) dbt Models & Tests

Install & init:

```bash
pip install dbt-redshift
# configure profiles.yml to read env vars (env_var('RS_HOST'), etc.)
dbt debug
```

**Sources** (`dbt/clickstream/models/_sources.yml`):
```yaml
version: 2
sources:
  - name: raw
    schema: raw
    tables:
      - name: raw_clicks
```

**Staging** (`stg_clicks.sql`):
```sql
{{ config(materialized='view') }}
select
  event_id, customer_id, session_id, event_type, page,
  utm_campaign, device, geo_city, event_ts, dt
from {{ source('raw','raw_clicks') }};
```

**Mart** (`fct_sessions.sql`):
```sql
{{ config(materialized='table') }}
with s as (
  select
    customer_id, session_id,
    min(event_ts) as session_start,
    max(event_ts) as session_end,
    count(*) as events,
    sum(case when event_type='checkout' then 1 else 0 end) as checkouts
  from {{ ref('stg_clicks') }}
  group by 1,2
)
select
  *,
  datediff('minute', session_start, session_end) as session_minutes,
  case when checkouts > 0 then 1 else 0 end as converted
from s;
```

**Tests** (`schema.yml`):
```yaml
version: 2
models:
  - name: stg_clicks
    columns:
      - name: event_id
        tests: [not_null]
      - name: customer_id
        tests: [not_null]
  - name: fct_sessions
    columns:
      - name: session_id
        tests: [not_null]
      - name: converted
        tests:
          - accepted_values: { values: [0,1] }
```

Run:
```bash
# ensure dbt sees your .env
python -m dotenv -f .env run -- dbt run
python -m dotenv -f .env run -- dbt test
```

---

## 6) Superset Dashboard

1. **Connect DB**: Settings → Database Connections → Amazon Redshift  
   URI: `redshift+psycopg2://RS_USER:RS_PWD@RS_HOST:RS_PORT/RS_DB`
2. **Datasets**:
   - `fct_sessions` (temporal: `session_start`)
   - `stg_clicks` (temporal: `event_ts`)
3. **Metrics**:
   - `sessions = COUNT(DISTINCT session_id)`
   - `conversion_rate = AVG(converted)`
   - `avg_session_minutes = AVG(session_minutes)`
   - `events = COUNT(*)` (in `stg_clicks`)
4. **Charts** (add to a dashboard “Clickstream Overview”):
   - Big Numbers: Sessions (7d), Conversion Rate, Avg Session Minutes, Checkouts
   - Time series: Sessions per day; Conversion rate (%)
   - Bars: Top pages; Device share; UTM campaigns (traffic & checkouts)
   - Heatmap: events by hour × weekday
   - Table: latest 100 events

---

## 7) Airflow (Hourly Automation)

DAG (`airflow_home/dags/clicks_redshift_dag.py`):
- Task 1: `COPY` last partition from S3 ➜ `raw.raw_clicks`
- Task 2: `dbt run`
- Task 3: `dbt test`

Run locally:
```bash
pip install "apache-airflow==2.10.1" python-dotenv
export AIRFLOW_HOME=./airflow_home
airflow db init
airflow users create --username admin --password admin --firstname A --lastname B --role Admin --email a@b.c
airflow webserver -p 8080 & airflow scheduler
```

---

## 8) (Optional) Terraform

- `terraform/main.tf`: create S3 bucket, IAM role for Redshift, (optionally) Redshift cluster/serverless
- Usage:
```bash
cd terraform
terraform init
terraform apply -var="bucket=$S3_BUCKET" -var="region=$AWS_REGION"
```

---

## 📊 Data Model (what you get)

- **`raw.raw_clicks`**: raw-ish events loaded from S3 Parquet (append-only, partitioned by `dt`)
- **`stg_clicks`**: cleaned staging layer over raw clicks (view or table)
- **`fct_sessions`**: session-level fact with:
  - `session_start`, `session_end`, `session_minutes`
  - `events`, `checkouts`, `converted` (0/1)

---

## 🧪 Testing & Validation

- dbt tests: `not_null`, `accepted_values`
- Sanity SQL:
```sql
select count(*) from raw.raw_clicks;
select * from staging_raw.fct_sessions order by session_start desc limit 20;
```

---

## 🛠️ Troubleshooting

- **Spark → S3 errors**: add `hadoop-aws` & `aws-java-sdk-bundle` jars to Spark; verify `.env` keys.
- **Redshift COPY fails**: check `RS_ROLE_ARN` attached to workgroup/cluster; correct `region`; ensure partition path exists.
- **dbt compile error (source not found)**: ensure `_sources.yml` has `schema: raw` and `tables: [raw_clicks]`; model uses `{{ source('raw','raw_clicks') }}`.
- **Superset charts empty**: set dataset **temporal column** and dashboard **time range**.

---

## 📄 License
MIT (or your preferred license)

---

## 📌 Resume Snippet

> Built a streaming **ELT** pipeline (Kafka → Spark → S3 → Redshift → dbt) with Airflow orchestration and Superset dashboards; delivered sessions & conversion KPIs with tested dbt models and reproducible infra.


