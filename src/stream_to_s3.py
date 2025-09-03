from dotenv import load_dotenv; load_dotenv()

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import *
import os
import pyspark

SPARK_VER = pyspark.__version__          # e.g. "3.5.1"
SCALA_SUFFIX = "2.12"

S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")



schema = StructType([
    StructField("event_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("session_id", StringType()),
    StructField("event_type", StringType()),
    StructField("page", StringType()),
    StructField("utm_campaign", StringType()),
    StructField("device", StringType()),
    StructField("geo_city", StringType()),
    StructField("event_ts", StringType()),
    StructField("source", StringType())
])

BASE = "/home/ouyassine/spark-jars"  # no spaces!

spark = (
    SparkSession.builder
    .appName("clicks-to-s3")
    .config("spark.sql.shuffle.partitions", "4")

    # S3A
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")

    # ✅ Force correct region; DO NOT set endpoint from env
    .config("spark.hadoop.fs.s3a.region", "us-east-1")
    .config("spark.hadoop.fs.s3a.bucket.rcml-clicks.region", "us-east-1")

    # Optional: explicitly set the regional endpoint (either keep this, or omit it)
    .config("spark.hadoop.fs.s3a.endpoint", "s3.us-east-1.amazonaws.com")

    # If you previously set any timeouts/YARN overrides, keep those too
    .config("spark.hadoop.fs.s3a.connection.timeout", "60000")
    .config("spark.hadoop.fs.s3a.connection.establish.timeout", "60000")
    .config("spark.hadoop.fs.s3a.retry.interval", "1000")
    .config("spark.hadoop.fs.s3a.threads.keepalivetime", "60")
    .config("spark.hadoop.yarn.router.subcluster.cleaner.interval.time", "60000")
    .config("spark.hadoop.yarn.resourcemanager.delegation-token-renewer.thread-retry-interval", "60000")
    .config("spark.hadoop.yarn.resourcemanager.delegation-token-renewer.thread-timeout", "60000")
    .config("spark.hadoop.yarn.resourcemanager.delegation-token.max-lifetime", "86400000")
    .config("spark.hadoop.yarn.resourcemanager.delegation-token.renew-interval", "86400000")
    .getOrCreate()
)

hconf = spark._jsc.hadoopConfiguration()
it = hconf.iterator()
to_fix = []
while it.hasNext():
    e = it.next()
    val = str(e.getValue())
    if val.endswith(("s","m","h")) and any(t in val for t in ("60s","24h")):
        to_fix.append(e.getKey())

for k in to_fix:
    v = hconf.get(k)
    if v == "60s":
        hconf.set(k, "60000")      # ms
    elif v == "24h":
        hconf.set(k, "86400000")   # ms

# sanity: print any lingering duration-like values
it = hconf.iterator()
left = []
while it.hasNext():
    e = it.next()
    if any(x in str(e.getValue()) for x in ("60s","24h")):
        left.append((e.getKey(), e.getValue()))
print("Still duration-form props:", left)

hconf = spark.sparkContext._jsc.hadoopConfiguration()
hconf.set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
hconf.set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
hconf.set("fs.s3a.impl","org.apache.hadoop.fs.s3a.S3AFileSystem")

raw = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
       .option("subscribe", "clicks")
       .option("startingOffsets","earliest")
       .option("kafkaConsumer.pollTimeoutMs", "60000")
       .option("fetchOffset.retryIntervalMs", "1000")
       .load())


parsed = (
  raw.selectExpr("CAST(value AS STRING) as json_str")
     .select(from_json(col("json_str"), schema).alias("d"))
     .select("d.*")
     .withColumn("event_ts", to_timestamp("event_ts"))  # <- cast to timestamp
     .withColumn("event_time", col("event_ts"))
     .withColumn("dt", col("event_ts").cast("date"))
)

(
parsed.writeStream
 .format("parquet")                          # simple Parquet bronze
 .option("path", f"s3a://{S3_BUCKET}/bronze/clicks/")
 .option("checkpointLocation", f"s3a://{S3_BUCKET}/chk/bronze/clicks/")
 .partitionBy("dt")
 .outputMode("append")
 .start()
 .awaitTermination()
)


