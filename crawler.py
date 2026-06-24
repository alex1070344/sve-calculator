import requests
from bs4 import BeautifulSoup
import csv
import time

# 🌟 任務清單大擴充：加入了所有預組與特殊的 PR 卡網址
urls = [
    # === 補充包 (Booster Packs) ===
    "https://yuyu-tei.jp/sell/sev/s/bp20#newest", "https://yuyu-tei.jp/sell/sev/s/bp19", 
    "https://yuyu-tei.jp/sell/sev/s/bp18", "https://yuyu-tei.jp/sell/sev/s/bp17",
    "https://yuyu-tei.jp/sell/sev/s/bp16", "https://yuyu-tei.jp/sell/sev/s/bp15",
    "https://yuyu-tei.jp/sell/sev/s/bp14", "https://yuyu-tei.jp/sell/sev/s/bp13",
    "https://yuyu-tei.jp/sell/sev/s/bp12", "https://yuyu-tei.jp/sell/sev/s/bp11",
    "https://yuyu-tei.jp/sell/sev/s/bp10", "https://yuyu-tei.jp/sell/sev/s/bp09",
    "https://yuyu-tei.jp/sell/sev/s/bp08", "https://yuyu-tei.jp/sell/sev/s/bp07",
    "https://yuyu-tei.jp/sell/sev/s/bp06", "https://yuyu-tei.jp/sell/sev/s/bp05",
    "https://yuyu-tei.jp/sell/sev/s/bp04", "https://yuyu-tei.jp/sell/sev/s/bp03",
    "https://yuyu-tei.jp/sell/sev/s/bp02", "https://yuyu-tei.jp/sell/sev/s/bp01",
    
    # === 合作/額外包 (Collaboration / Extra) ===
    "https://yuyu-tei.jp/sell/sev/s/cp04", "https://yuyu-tei.jp/sell/sev/s/cp03",
    "https://yuyu-tei.jp/sell/sev/s/cp02", "https://yuyu-tei.jp/sell/sev/s/cp01",
    "https://yuyu-tei.jp/sell/sev/s/ecp02", "https://yuyu-tei.jp/sell/sev/s/ecp01",
    "https://yuyu-tei.jp/sell/sev/s/sp01", "https://yuyu-tei.jp/sell/sev/s/pcs01",

    # === 預組/新手牌組 (Starter / Beginner Decks) ===
    "https://yuyu-tei.jp/sell/sev/s/ebd04", "https://yuyu-tei.jp/sell/sev/s/ebd03",
    "https://yuyu-tei.jp/sell/sev/s/ebd02", "https://yuyu-tei.jp/sell/sev/s/ebd01",
    "https://yuyu-tei.jp/sell/sev/s/dsd01",
    "https://yuyu-tei.jp/sell/sev/s/csd03", "https://yuyu-tei.jp/sell/sev/s/csd02", "https://yuyu-tei.jp/sell/sev/s/csd01",
    "https://yuyu-tei.jp/sell/sev/s/etd03", "https://yuyu-tei.jp/sell/sev/s/etd02", "https://yuyu-tei.jp/sell/sev/s/etd01",
    "https://yuyu-tei.jp/sell/sev/s/sd08", "https://yuyu-tei.jp/sell/sev/s/sd07", 
    "https://yuyu-tei.jp/sell/sev/s/sd06", "https://yuyu-tei.jp/sell/sev/s/sd05",
    "https://yuyu-tei.jp/sell/sev/s/sd04", "https://yuyu-tei.jp/sell/sev/s/sd03", 
    "https://yuyu-tei.jp/sell/sev/s/sd02", "https://yuyu-tei.jp/sell/sev/s/sd01",

    # === 特典卡 / PR 卡 (Promotion Cards) ===
    "https://yuyu-tei.jp/sell/sev/s/pr-600",
    "https://yuyu-tei.jp/sell/sev/s/pr-500",
    "https://yuyu-tei.jp/sell/sev/s/pr-400",
    "https://yuyu-tei.jp/sell/sev/s/pr-300",
    "https://yuyu-tei.jp/sell/sev/s/pr-200",
    "https://yuyu-tei.jp/sell/sev/s/pr-101"
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}

print("啟動連續抓取機器人...\n")

with open("cards_price.csv", "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["卡號", "價格", "圖片網址", "卡名"]) 
    
    total_cards = 0
    for url in urls:
        print(f"正在潛入：{url}")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", class_="card-product")
            
            for card in cards:
                card_id_tag = card.find("span", class_="border-dark")
                price_tag = card.find("strong", class_="text-end")
                img_tag = card.find("img", class_="card img-fluid")
                name_tag = card.find("h4", class_="text-primary fw-bold") 
                
                if card_id_tag and price_tag:
                    card_id = card_id_tag.text.strip()
                    price = price_tag.text.replace(",", "").replace("円", "").strip()
                    img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
                    card_name = name_tag.text.strip() if name_tag else "未知卡名"
                    
                    writer.writerow([card_id, price, img_url, card_name])
                    total_cards += 1
            time.sleep(2) # 休息兩秒，保護網路連線

print("-" * 30)
print(f"🎉 全部收錄了 {total_cards} 張卡片！")