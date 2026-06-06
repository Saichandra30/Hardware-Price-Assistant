import time
from llm.hybrid_client import HybridClient

client = HybridClient()

print('--- EXACT MATCH ---')
start = time.perf_counter()
for event in client.generate_response_stream('9700X'):
    if event['type'] == 'text':
        print('TEXT:', event['data'])
end = time.perf_counter()
print(f'Time: {end - start:.4f}s\n')

print('--- BRAND MATCH ---')
start = time.perf_counter()
for event in client.generate_response_stream('asus'):
    if event['type'] == 'text':
        print('TEXT:', event['data'])
end = time.perf_counter()
print(f'Time: {end - start:.4f}s\n')

print('--- RECOMMENDATION MATCH ---')
start = time.perf_counter()
for event in client.generate_response_stream('best motherboard for 9700x'):
    if event['type'] == 'text':
        print('TEXT:', event['data'])
end = time.perf_counter()
print(f'Time: {end - start:.4f}s\n')

print('--- LLM MATCH ---')
start = time.perf_counter()
for event in client.generate_response_stream('what is the difference between a cpu and a gpu?'):
    pass
end = time.perf_counter()
print(f'Time: {end - start:.4f}s\n')
