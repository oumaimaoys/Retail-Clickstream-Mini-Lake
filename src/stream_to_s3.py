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

jar_list=",".join([
    f"{BASE}/spark-sql-kafka-0-10_2.12-4.0.0.jar",
    f"{BASE}/spark-token-provider-kafka-0-10_2.12-4.0.0.jar",
    f"{BASE}/kafka-clients-3.7.0.jar",
    f"{BASE}/commons-pool2-2.12.0.jar",
    f"{BASE}/hadoop-aws-3.3.6.jar",
    f"{BASE}/aws-java-sdk-bundle-1.12.367.jar",
    f"{BASE}/lz4-java-1.8.0.jar",
    f"{BASE}/snappy-java-1.1.10.5.jar",
])

spark = (
    SparkSession.builder
    .appName("clicks-to-s3")
    # put jars everywhere
    .config("spark.jars", jar_list)
    .config("spark.driver.extraClassPath", jar_list.replace(",", ":"))
    .config("spark.executor.extraClassPath", jar_list.replace(",", ":"))
    .config("spark.sql.shuffle.partitions", "4")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_REGION}.amazonaws.com")
    .getOrCreate()
)

# sanity check – will raise if kafka provider isn't on classpath
_ = spark._jvm.org.apache.spark.sql.kafka010.KafkaSourceProvider

print("Kafka provider:", spark._jvm.org.apache.spark.sql.kafka010.KafkaSourceProvider)


hconf = spark.sparkContext._jsc.hadoopConfiguration()
hconf.set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
hconf.set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
hconf.set("fs.s3a.impl","org.apache.hadoop.fs.s3a.S3AFileSystem")

raw = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
       .option("subscribe", "clicks")
       .option("startingOffsets","earliest")
       .load())


parsed = (raw.selectExpr("CAST(value AS STRING) as json_str")
            .select(from_json(col("json_str"), schema).alias("d"))
            .select("d.*")
            .withColumn("event_time", to_timestamp("event_ts"))
            .withColumn("dt", col("event_time").cast("date")))

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


