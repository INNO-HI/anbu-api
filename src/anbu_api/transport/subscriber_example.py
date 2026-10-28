"""참여 대학용 구독 수신 예제(SFR-006).

가명처리된 전송본을 구독해 수신하고, 수신 확인을 anbu/receipts/<client_id>로
발행한다. 참여 대학에 배포하는 샘플 코드이며 본교 서버에서는 실행하지 않는다.

사용 예:
  python -m anbu_api.transport.subscriber_example \
      --host <broker> --port 8883 --ca ca.crt \
      --client-id univ_a --username univ_a --password '***' \
      --topics 'anbu/subjects' 'anbu/alerts'

수신한 전송본의 관리 책임은 참여 대학에 있으며, 보안 약정(재식별 시도 금지,
목적 외 이용·제3자 제공 금지, 기간 종료 시 파기·통보)을 준수해야 한다.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

import paho.mqtt.client as mqtt


def main() -> None:
    parser = argparse.ArgumentParser(description="anbu 전송본 구독 수신 예제")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--ca", help="브로커 CA 인증서 경로(TLS)")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--topics", nargs="+", default=["anbu/#"])
    parser.add_argument("--out", default="received.jsonl", help="수신 데이터 저장 파일")
    args = parser.parse_args()

    received = Counter()
    out = open(args.out, "a", encoding="utf-8")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv5,
    )
    if args.username:
        client.username_pw_set(args.username, args.password)
    if args.ca:
        client.tls_set(ca_certs=args.ca)

    def on_message(cli, userdata, msg):
        received[msg.topic] += 1
        out.write(json.dumps({"topic": msg.topic, "data": json.loads(msg.payload)},
                             ensure_ascii=False) + "\n")
        # 100건마다 수신 확인 발행(제공 실적 집계용)
        if received[msg.topic] % 100 == 0:
            cli.publish(
                f"anbu/receipts/{args.client_id}",
                json.dumps({"topic": msg.topic, "record_count": 100}),
                qos=1,
            )

    client.on_message = on_message
    client.connect(args.host, args.port)
    for topic in args.topics:
        client.subscribe(topic, qos=1)
    print(f"구독 시작: {args.topics} (Ctrl+C로 종료)")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        # 종료 시 잔여 수신분 확인 발행
        for topic, n in received.items():
            client.publish(
                f"anbu/receipts/{args.client_id}",
                json.dumps({"topic": topic, "record_count": n % 100}),
                qos=1,
            )
        client.disconnect()
        out.close()


if __name__ == "__main__":
    main()
