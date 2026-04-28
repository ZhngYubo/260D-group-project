import pandas as pd

# 读取大文件时可用chunksize分块处理，避免内存占用过高
csv_path = 'data/opensky_lax_segments_with_runway.csv'
runway_counts = {}

for chunk in pd.read_csv(csv_path, usecols=["runway"], chunksize=100000):
    counts = chunk["runway"].value_counts()
    for runway, count in counts.items():
        runway_counts[runway] = runway_counts.get(runway, 0) + count

print("各跑道数据量统计：")
for runway, count in sorted(runway_counts.items()):
    print(f"{runway}: {count}")
