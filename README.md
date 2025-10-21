# Retail Clickstream Mini-Lake

This project is a streaming ELT application that simulates website clickstream data and turns it into business-ready analytics. It ingests events into Kafka, streams them to S3 with PySpark, loads them into Amazon Redshift, models marts with dbt, and visualizes KPIs in Apache Superset.

## Features
- User-friendly, reproducible local setup with Docker (Kafka + UI)
- Real-time event generation and ingestion (Kafka → PySpark Structured Streaming → S3 Parquet)
- Automated Redshift loading via COPY from S3
- Analytics modeling with dbt (staging + facts with tests)
- Superset dashboard for sessions, conversion rate, top pages/devices, funnels
- Airflow DAG for hourly orchestration
- Terraform for S3, IAM, and Redshift provisioning

## Technologies Used
**Backend / Data:**
- Python, PySpark (Structured Streaming), Apache Kafka
- Amazon S3 (data lake), Amazon Redshift (warehouse)
- dbt-redshift (models, tests), Apache Airflow (orchestration, optional)
- Terraform, Docker / docker-compose

**Frontend / Visualization:**
- Apache Superset (dashboards)

## Setup and Installation
1. **Clone the repository**
2. **Create a `.env` file** at the project root (do not commit secrets):
   ```env
   AWS_REGION=eu-west-1
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   S3_BUCKET=rcml-clicks-yourname

   KAFKA_BOOTSTRAP=localhost:9092

   RS_HOST=your-redshift-endpoint.region.redshift.amazonaws.com
   RS_DB=dev
   RS_USER=awsuser
   RS_PWD=SuperSecret123
   RS_PORT=5439
   RS_ROLE_ARN=arn:aws:iam::<acct>:role/RedshiftS3Read
   ```
3. **Start Kafka locally** (Docker):
   ```bash
   docker compose -f docker/docker-compose.kafka.yml up -d
   ```
4. **Install Python requirements** (generator + streaming):
   ```bash
   pip install -r requirements.txt  
   pip install pyspark==3.5.1 python-dotenv
   ```
5. **Run the clickstream generator** (produces events into Kafka):
   ```bash
   python src/clickstream_generator.py
   ```
6. **Run the streaming job to S3 (bronze Parquet)**:
   ```bash
   BASE=spark-jars

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
   ```
7. **Create Redshift schema/table and COPY data** (in Query Editor v2):
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

   copy raw.raw_clicks
   from 's3://rcml-clicks-yourname/bronze/clicks/dt=2025-08-24/'
   iam_role 'arn:aws:iam::<acct>:role/RedshiftS3Read'
   format as parquet
   region 'eu-west-1';
   ```
8. **Install and run dbt** (models + tests):
   ```bash
   pip install dbt-redshift
   python -m dotenv -f .env run -- dbt run
   python -m dotenv -f .env run -- dbt test
   ```
9. **Connect Superset to Redshift** and build the dashboard (see Usage).

## Usage
1. **Kafka stream running** and **Spark writing to S3**.
2. **Redshift COPY** new partitions from S3 into `raw.raw_clicks` (manually or via Airflow).
3. **dbt run/test** to build:
   - `stg_clicks` (staging view/table over `raw.raw_clicks`)
   - `fct_sessions` (session-level fact with KPIs)
4. **Superset**:
   - Add a Redshift database connection.
   - Register datasets: `fct_sessions` (temporal: `session_start`), `stg_clicks` (temporal: `event_ts`).
   - Add charts to a dashboard (Clickstream Overview):
     - Big Numbers: Sessions (Last 7d), Conversion Rate, Avg Session Minutes, Checkouts
     - Time Series: Sessions per day; Conversion rate (%)
     - Bars: Top pages; Device share; UTM campaigns (traffic & checkouts)
     - Heatmap: Events by hour × weekday
     - Table: Latest 100 events

## File Structure
- `src/clickstream_producer.py`: event generator to Kafka
- `src/stream_to_s3.py`: Spark Structured Streaming writer to S3 (Parquet bronze)
- `dags/clickstream/models/_sources.yml`: dbt source for `raw.raw_clicks`
- `dags/clickstream/models/stg_clicks.sql`: staging model
- `dags/clickstream/models/fct_sessions.sql`: session-level fact
- `dags/clickstream/models/schema.yml`: dbt tests
- `dags/clicks_redshift_dag.py`:  hourly COPY + dbt DAG
- `docker/docker-compose.kafka.yml`: Kafka + UI
- `terraform/`: S3, IAM role, Redshift
- `.env`: environment variables (not committed)



