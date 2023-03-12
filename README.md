# 웹챗 (WebChat)
### 유저들 간 실시간 채팅을 할 수 있는 서비스

## Prerequisites
> 언어
- Python 3.10.4

> 웹 프레임워크
- FastAPI 0.87.0

> 데이터베이스
- MySQL 8.0.32

## AWS EC2 Deployment
- nginx.conf 파일 추가 (path: websocket / client / nginx.conf)
```
    ...
    upstream backend_app {
       server backend-container:8000;
    }
    
    server {
        listen       80;
        listen       [::]:80;
        server_name  _;
        root         /usr/share/nginx/html;
        index        index.html;
    
        error_page 404 /404.html;
        location = /404.html {
        }
    
        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
        }
    
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
        }
    
        location /api {
            proxy_pass http://backend_app;
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-NginX-Proxy true;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_http_version 1.1;
    
            proxy_pass_header Set-Cookie;
            proxy_pass_header X-CSRFToken;
            proxy_redirect off;
            proxy_buffering off;
        }
        location /docs {
            proxy_pass http://backend_app;
        }
        location /openapi.json {
            proxy_pass http://backend_app;
        }
    }
}
```
- .env 파일 추가 (path: websocket / server / .env)
```dotenv
DB_NAME="websocket"
DB_USERNAME=""
DB_PASSWORD=""
DB_HOST=""
DB_PORT=3306

BACKEND_CORS_ORIGINS=[""]

DEBUG=false

SESSION_SECRET_KEY=""

REDIS_ENDPOINT=[""]
REDIS_DATABASE=0

AWS_ACCESS_KEY=""
AWS_SECRET_ACCESS_KEY=""
AWS_STORAGE_BUCKET_NAME=""
AWS_CDN_URL=""
```

- 도커 이미지 빌드 및 컨테이너 실행
```shell
$ docker-compose up --build -d
```

## Flow
```mermaid
sequenceDiagram
autonumber
actor A as Client
participant B as Server
participant C as Redis
participant D as Database
participant E as AWS S3

A ->> B: 회원 가입
activate B
B ->> D: 유저 및 유저 프로필 데이터 생성
B ->> C: 데이터 동기화
B ->> A: 성공
deactivate B

A ->> B: 로그인
activate B
B ->> D: 유저 데이터 조회
B ->> D: 세션 ID 생성하여 세션 테이블에 저장
B ->> B: 응답 데이터에 세션 정보 담은 쿠키 설정
B ->> A: 성공
deactivate B

A ->> B: 친구/대화방 목록 웹소켓 연결
activate B
loop 
    B ->> C: 요청한 유저 및 대화방, 팔로우 데이터 요청
    C ->> B: 데이터 전달
    opt 데이터 없는 경우
        B ->> D: Redis 로부터 전달 받지 못한 데이터 요청
        D ->> B: 데이터 전달
        B ->> C: 데이터 동기화
    end
end
B ->> A: 친구/대화방 목록 데이터 전달
deactivate B

A ->> B: 유저 프로필 검색 (웹챗 ID 검색)
activate B
B ->> D: 유저 프로필 조회
B ->> A: 성공
deactivate B

A ->> B: 팔로우 추가
activate B
B ->> D: 유저 관계 테이블 데이터 생성
B ->> C: 데이터 동기화
B ->> A: 성공
deactivate B

A ->> B: 대화방 생성 (1:1, 1:N)
activate B
alt 1:1 대화방 생성인 경우
    opt 기존 데이터 존재하지 않는 경우
        B ->> D: 방 데이터 생성 및 유저 연결
        B ->> C: 데이터 동기화
    end
else
    B ->> D: 방 데이터 생성 및 유저 연결
    B ->> C: 데이터 동기화
end
B ->> A: 성공 (방 데이터 전달)
deactivate B

A ->> B: 대화방 입장 시 웹소켓 연결
activate B
B ->> C: 방 관련 데이터 조회
opt 데이터 존재하지 않는 경우
    B ->> D: 데이터 조회
    B ->> C: 데이터 동기화
end
B ->> C: 대화방 메시지 읽음 처리

loop
    opt 메시지 조회 요청을 수신한 경우
        B ->> C: 메시지 조회 (offset, limit)
        opt Redis 데이터가 부족한 경우
            B ->> D: 메시지 조회 및 메시지 읽음 처리
        end
    end
    opt 메시지 업데이트 요청을 수신한 경우
        B ->> C: 데이터 업데이트
        opt 요청한 메시지가 Redis 에 없는 경우
            B ->> D: 데이터 업데이트
        end
    end
    opt 메시지 전송 요청을 수신한 경우
        B ->> C: 메시지 저장
        B ->> C: 방에 연결된 유저 별 메시지 읽음 처리
    end
    opt 파일 업로드 요청을 수신한 경우
        B ->> B: base64 디코딩 및 BytesIO 변환
        B ->> E: 비동기 파일 업로드
        B ->> D: 파일 저장
        B ->> C: 데이터 동기화
    end
    opt 유저 초대 요청을 수신한 경우
        B ->> D: 방에 초대한 유저 데이터 추가
        B ->> C: 데이터 동기화
    end
    opt 연결 종료 요청을 수신한 경우
        B ->> D: 해당 유저에 대한 연결 데이터 삭제
        B ->> C: 데이터 동기화
    end
    alt 브로드캐스트 전송인 경우
        B -) C: 데이터 Publish
        opt Subscribe 하여 데이터를 가져온 경우
            C -) B: 데이터 전달
            C -) A: 브로드캐스트 전송
        end
    else
        B ->> A: 유니캐스트 전송
    end
end
deactivate B
```

## Infra
- Webchat EC2 1대 (Filebeat 설치)
- Kafka EC2 2대 (Filebeat 설치)
- Zookeeper EC2 3대
- NiFi & ElasticSearch & Kibana EC2 1대
- 로그 모니터링 환경 구성
```mermaid
flowchart LR
subgraph Webchat
Filebeat001
end

Filebeat001 --> KafkaConsumer001

subgraph Kafka
kk1((Kafka001)) --> Filebeat002
kk2((Kafka002)) --> Filebeat003
end

Filebeat002 --> KafkaConsumer002
Filebeat003 --> KafkaConsumer002

subgraph NiFi
KafkaConsumer001 --> PutElasticSearch001
KafkaConsumer002 --> PutElasticSearch002
end

PutElasticSearch001 --> es[(ElasticSearch)]
PutElasticSearch002 --> es[(ElasticSearch)]
es[(ElasticSearch)] --> kb{Kiabana}
```

## Production
- IP address: http://13.125.196.205/