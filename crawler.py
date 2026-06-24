import requests
from bs4 import BeautifulSoup
import csv
import time  # 🌟 新裝備：時間控制器，用來讓機器人休息

# 1. 準備一個「任務清單」，把你想抓的卡包網址都貼進來
# 注意：網址要用引號包起來，每個網址之間要用「逗號」隔開！
urls = [
    "https://yuyu-tei.jp/sell/sev/s/bp20#newest",  # 第 20 彈
    "https://yuyu-tei.jp/sell/sev/s/bp19",  # 第 19 彈
    "https://yuyu-tei.jp/sell/sev/s/bp18",   # 第 18 彈
    "https://yuyu-tei.jp/sell/sev/s/bp17",
    "https://yuyu-tei.jp/sell/sev/s/bp16",
    "https://yuyu-tei.jp/sell/sev/s/bp15",
    "https://yuyu-tei.jp/sell/sev/s/bp14",
    "https://yuyu-tei.jp/sell/sev/s/bp13",
    "https://yuyu-tei.jp/sell/sev/s/bp12",
    "https://yuyu-tei.jp/sell/sev/s/bp11",
    "https://yuyu-tei.jp/sell/sev/s/bp10",
    "https://yuyu-tei.jp/sell/sev/s/bp09",
    "https://yuyu-tei.jp/sell/sev/s/bp08",
    "https://yuyu-tei.jp/sell/sev/s/bp07",
    "https://yuyu-tei.jp/sell/sev/s/bp06",
    "https://yuyu-tei.jp/sell/sev/s/bp05",
    "https://yuyu-tei.jp/sell/sev/s/bp04",
    "https://yuyu-tei.jp/sell/sev/s/bp03",
    "https://yuyu-tei.jp/sell/sev/s/bp02",
    "https://yuyu-tei.jp/sell/sev/s/bp01",
    "https://yuyu-tei.jp/sell/sev/s/cp04",
    "https://yuyu-tei.jp/sell/sev/s/cp03",
    "https://yuyu-tei.jp/sell/sev/s/cp02",
    "https://yuyu-tei.jp/sell/sev/s/cp01",
    "https://yuyu-tei.jp/sell/sev/s/ecp02",
    "https://yuyu-tei.jp/sell/sev/s/ecp01",
    "https://yuyu-tei.jp/sell/sev/s/sp01",
    "https://yuyu-tei.jp/sell/sev/s/pcs01"
    # 如果你想抓更多，可以繼續往下加（例如預組 deck 的網址）
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

print("啟動連續抓取機器人...\n")

# 2. 打開筆記本 (這步必須放在最外面，不然檔案會被一直覆蓋清空)
with open("cards_price.csv", "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["卡號", "價格"])
    
    total_cards = 0  # 幫你計算總共抓了幾張卡
    
    # 3. 讓機器人看著清單，一個網址一個網址去跑 (迴圈)
    for url in urls:
        print(f"正在潛入：{url}")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", class_="card-product")
            
            # 把這個網頁裡的卡片一張張寫進去
            for card in cards:
                card_id_tag = card.find("span", class_="border-dark")
                price_tag = card.find("strong", class_="text-end")
                
                if card_id_tag and price_tag:
                    card_id = card_id_tag.text.strip()
                    price = price_tag.text.replace(",", "").replace("円", "").strip()
                    writer.writerow([card_id, price])
                    total_cards += 1
                    
            print("✅ 任務完成！機器人休息 2 秒鐘...\n")
            # 🌟 爬蟲保命符：強迫機器人暫停 2 秒，保護你的網路不被封鎖
            time.sleep(2)  
            
        else:
            print(f"😢 連線失敗，錯誤代碼：{response.status_code}")

print("-" * 30)
print(f"🎉 全部卡包抓取完畢！總共收錄了 {total_cards} 張卡片！")