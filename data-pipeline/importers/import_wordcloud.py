import mysql.connector
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
p2021 = PROJECT_ROOT / "frontend" / "src" / "assets" / "zhejiang2021.png"
p2025 = PROJECT_ROOT / "frontend" / "src" / "assets" / "zhejiang2025.png"

def read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()

conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="000000",          # 改成你的
    database="teaching_awards",  # 改成你实际使用的库名
    charset="utf8mb4"
)

cur = conn.cursor()

sql = """
INSERT INTO wordcloud_images (year, filename, mime_type, img)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  filename=VALUES(filename),
  mime_type=VALUES(mime_type),
  img=VALUES(img);
"""

cur.execute(sql, (2021, "zhejiang2021.png", "image/png", read_bytes(p2021)))
cur.execute(sql, (2025, "zhejiang2025.png", "image/png", read_bytes(p2025)))

conn.commit()
cur.close()
conn.close()

print("✅ 2021/2025 词云图已写入 MySQL：wordcloud_images")
