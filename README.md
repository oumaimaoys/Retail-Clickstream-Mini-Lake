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


