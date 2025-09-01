import json, time, uuid, random
from datetime import datetime, timezone
from kafka import KafkaProducer

pages = ["/", "/home", "/category/shoes", "/product/sku-100", "/cart", "/checkout"]
events = ["page_view","view_product","add_to_cart","checkout"]
devices = ["mobile","desktop","tablet"]
cities = ["Rabat","Casablanca","Agadir","Fes","Tanger"]

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda v: v.encode("utf-8"),
)

customers = [f"c_{str(i).zfill(6)}" for i in range(1, 5001)]

while True:
    cid = random.choice(customers)
    evt = {
        "event_id": str(uuid.uuid4()),
        "customer_id": cid,
        "session_id": str(uuid.uuid4())[:18],
        "event_type": random.choices(events, weights=[0.6,0.25,0.1,0.05])[0],
        "page": random.choice(pages),
        "utm_campaign": random.choice(["summer-sale","retargeting","email","brand"]),
        "device": random.choice(devices),
        "geo_city": random.choice(cities),
        "event_ts": datetime.now(timezone.utc).isoformat(),
        "source": "web"
    }
    producer.send("clicks", key=cid, value=evt)
    time.sleep(0.1)  # 10 events/sec
