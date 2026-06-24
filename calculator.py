import csv

# 1. 把我們剛剛抓下來的價格表讀進電腦的記憶體裡
prices = {}
with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
    reader = csv.reader(file)
    next(reader)  # 跳過第一行的標題 ["卡號", "價格"]
    
    for row in reader:
        card_id = row[0]
        price = int(row[1])  # int() 的意思是把乾淨的文字轉換成「可計算的整數」
        prices[card_id] = price

# ==========================================

# 2. 假設這是你想組的【預組牌組】需求卡表
deck_list = {
    "BP20-U01": 3,  # 需要 3 張
    "BP20-U02": 2,  # 需要 2 張
    "BP20-SL01": 1  # 需要 1 張
}

# 3. 假設這是你目前【實際擁有的庫存】
my_inventory = {
    "BP20-U01": 1,  # 已經抽到 1 張了 (所以還缺 2 張)
    "BP20-U02": 0   # 完全沒有 (缺 2 張)
    # BP20-SL01 沒寫代表你一張都沒有 (缺 1 張)
}

# ==========================================

# 4. 開始比對與計算！
total_cost = 0
print("\n📝 你的缺卡採購清單：")
print("-" * 35)

for card_id, required_qty in deck_list.items():
    # 去庫存找你有幾張這張卡，找不到就當作 0 張
    owned_qty = my_inventory.get(card_id, 0) 
    
    # 計算缺卡數量 (需求 - 擁有)
    missing_qty = required_qty - owned_qty
    
    # 如果缺卡數量大於 0，才需要買
    if missing_qty > 0:
        # 去價格表查這張卡的單價，查不到就當作 0 元
        card_price = prices.get(card_id, 0) 
        
        # 算出這張卡要花多少錢 (缺幾張 * 單價)
        cost = missing_qty * card_price
        total_cost += cost # 加到總花費裡面
        
        print(f"【{card_id}】缺少 {missing_qty} 張 | 單價 {card_price} 円 | 小計：{cost} 円")

print("-" * 35)
print(f"💰 補齊這副牌組總共需要花費：{total_cost} 円\n")