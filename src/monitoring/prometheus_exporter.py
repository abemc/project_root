#!/usr/bin/env python3
"""
軽量 Prometheus エクスポーター
- exposes /metrics with simple counters/gauges for ingestion/embedding
- run as: python -m src.monitoring.prometheus_exporter
"""
from prometheus_client import start_http_server, Counter, Gauge
import time
import argparse

INGEST_COUNTER = Counter('rag_ingest_docs_total', 'Total documents ingested')
EMBED_LATENCY = Gauge('rag_embed_last_latency_seconds', 'Last embed batch latency (s)')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8000)
    args = p.parse_args()
    start_http_server(args.port)
    print(f'Prometheus exporter listening on :{args.port}')
    # Dummy loop to show usage; real integration should increment counters
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print('stopping')

if __name__ == '__main__':
    main()
