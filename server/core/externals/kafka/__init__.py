# confluent-kafka-python, kafka-python 등 존재함
# 성능면에서 confluent-kafka-python 제일 빠름 (설치하려면 librdkafka(아파치 카프카 프로토콜의 C 라이브러리) 설치 필요)
# 성능 테스트 : http://www.popit.kr/kafka-python-client-성능-테스트 글 참조
from kafka import KafkaProducer

# bootstrap.servers에 브로커 리스트 지정 (카프카 클러스터 모두 추가해야 함 -> 하나의 호스트만 입력한 경우, 해당 호스트 다운 상태에서 다시 실행 시 오류 발생)
producer = KafkaProducer(
    acks=1, compression_type='gzip',
    bootstrap_servers='peter-kafka001:9092, peter-kafka002:9092, peter-kafka003:9092')
# 토픽명과 보낼 메시지의 내용을 지정하고 전송
# key 옵션을 지정하여 특정 파티션으로만 메시지 전송 가능 (없다면, 라운드로빈 방식으로 파티션마다 균등하게 메시지 전송)
producer.send('peter-topic', 'Apache Kafka is a distributed streaming platform')
for i in range(1, 11):
    if i % 2 == 1:
        producer.send('peter-topic2', key='1', value='%d - Apache Kafka is a distributed streaming platform - key=1' % i)
    else:
        producer.send('peter-topic2', key='2', value='%d - Apache Kafka is a distributed streaming platform - key=2' % i)

# EC2 컨슈머 실행
# /usr/local/kafka/bin/kafka-console-consumer.sh --bootstrap-server peter-kafka@001:9092,peter-kafka002:9092,peter-kafka003:9092 --topic peter-topic2 --from-beginning

