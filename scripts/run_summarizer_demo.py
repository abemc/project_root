#!/usr/bin/env python3
import json
from analyzer.llm_client import MockLLMClient
from analyzer.summarizer import summarize_files

TRACE_PATH = 'analysis_result_trace.json'
ROOT = '/home/abemc/project_root'

with open(TRACE_PATH, 'r', encoding='utf-8') as f:
    trace = json.load(f)

files = trace.get('files', [])[:50]
client = MockLLMClient()

out = summarize_files(files, ROOT, client, chunk_size=2000, map_reduce=True)
print('SUMMARY_LEN=', len(out))
print(out[:500])
