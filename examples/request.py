from time import sleep

import requests

# print("=== 测试非流式接口 ===")
# response = requests.post(
#     "http://localhost:8000/chat",
#     json={"question": "查看项目文件列表"}
# )
# print(f"type:{type(response.json())}\n\n")
# print(response.json())

print("\n\n=== 测试流式接口 ===")
for chunk in requests.post(
    "http://localhost:8000/chat/stream",
    json={"question": "查看项目文件列表"},
    stream=True
).iter_content(decode_unicode=True):
    print(chunk, end='', flush=True)



