import machine
import time
import framebuf
import epaper_driver # 先ほど成功したドライバをインポート

# ==========================================
# 1. キーパッド設定 (GPIO 0-7)
# ==========================================
# Row(行)を出力、Col(列)を入力(Pull-down)に設定
rows = [machine.Pin(i, machine.Pin.OUT) for i in range(4)]
cols = [machine.Pin(i, machine.Pin.IN, machine.Pin.PULL_DOWN) for i in range(4, 8)]

KEY_MAP = [
    ["1", "4", "7", "10"], # *=10pt
    ["2", "5", "8", "11"], # 0=11pt
    ["3", "6", "9", "12"], # #=12pt
    ["U", "0", "R", "B"]   # A=Undo, B=Miss, C=Reset, D=Burst(25)
]

def scan_keypad():
    for r_idx, row_pin in enumerate(rows):
        row_pin.value(1)
        for c_idx, col_pin in enumerate(cols):
            if col_pin.value() == 1:
                row_pin.value(0)
                return KEY_MAP[r_idx][c_idx]
        row_pin.value(0)
    return None

# ==========================================
# 2. ゲーム管理クラス
# ==========================================
class MolkkyGame:
    def __init__(self):
        # 1. ドライバの初期化（この時点でepd.init()が走ります）
        self.epd = epaper_driver.EPD_2in13_V4_Landscape()
        
        # 2. 画面の物理リフレッシュ（真っ白にする）
        print("Refreshing screen...")
        self.epd.Clear() 
        
        # Landscapeモード(横向き)を使用
        self.epd = epaper_driver.EPD_2in13_V4_Landscape()
        self.state = 0 # 0:設定, 1:試合中
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None # 1手前のみ保存
        self.msg = "Welcome!"
        
        # 4. 初期メニューの描画
        # self.draw()

    def draw(self):
        self.epd.fill(0xff) # 白
        
        if self.state == 0:
            self.epd.text("MOLKKY SCOREBOARD", 10, 10, 0)
            self.epd.text(f"Players: [{self.num_players}]", 10, 40, 0)
            self.epd.text("1-4:Set Num  A:Start", 10, 80, 0)
        else:
            p = self.players[self.cur_idx]
            self.epd.fill_rect(0, 0, 250, 18, 0) # 黒ヘッダー
            self.epd.text(f"Turn: {p['name']}", 10, 5, 0xff)
            
            # プレイヤーリスト表示
            for i, pl in enumerate(self.players):
                x = 10 if i < 2 else 135
                y = 30 + (i % 2) * 45
                mark = ">" if i == self.cur_idx else " "
                status = "OUT" if pl["out"] else f"{pl['score']}pt"
                self.epd.text(f"{mark}{pl['name']}: {status}", x, y, 0)
                self.epd.text(f"  M:{'X'*pl['miss']} S:{pl['sets']}", x, y+15, 0)
            
            self.epd.text(self.msg, 10, 110, 0)

        self.epd.display()

    def start_game(self):
        self.players = [{"name":f"P{i+1}", "score":0, "miss":0, "sets":0, "out":False} for i in range(self.num_players)]
        self.state = 1
        self.cur_idx = 0
        self.msg = "Game Start!"
        self.draw()

    def update_score(self, s):
        # Undo用に現状をコピー（簡易版）
        self.history = {"players": [dict(p) for p in self.players], "cur_idx": self.cur_idx}
        
        p = self.players[self.cur_idx]
        if s == 0:
            p["miss"] += 1
            if p["miss"] >= 3:
                p["out"] = True
                self.msg = f"{p['name']} is OUT!"
        else:
            p["miss"] = 0
            p["score"] += s
            if p["score"] == 50:
                p["sets"] += 1
                self.msg = f"{p['name']} Win Set!"
                self.reset_scores() # 全員0点に戻して次のセットへ
            elif p["score"] > 50:
                p["score"] = 25
                self.msg = "Over 50! Back to 25"
            else:
                self.msg = f"{p['name']} +{s}pt"

        self.next_turn()
        self.draw()

    def undo(self):
        if self.history:
            self.players = self.history["players"]
            self.cur_idx = self.history["cur_idx"]
            self.msg = "Undo!"
            self.history = None
            self.draw()

    def reset_scores(self):
        for p in self.players:
            p["score"] = 0
            p["miss"] = 0
            p["out"] = False

    def next_turn(self):
        for _ in range(self.num_players):
            self.cur_idx = (self.cur_idx + 1) % self.num_players
            if not self.players[self.cur_idx]["out"]:
                break

# ==========================================
# 3. メインループ
# ==========================================
game = MolkkyGame()
game.draw()

last_key = None
while True:
    key = scan_keypad()
    if key and key != last_key:
        print("key is {}".format(key))
        if game.state == 0:
            if key in ["1", "2", "3", "4"]:
                game.num_players = int(key)
                game.draw()
            elif key == "10": # Aボタンで開始
                game.start_game()
        
        elif game.state == 1:
            if key.isdigit() or key in ["10", "11", "12"]:
                game.update_score(int(key))
            elif key == "B": # Burst
                game.players[game.cur_idx]["score"] = 25
                game.msg = "Forced 25pt"
                game.next_turn()
                game.draw()
            elif key == "U": # Undo
                game.undo()
            elif key == "R": # 全リセット
                game.state = 0
                game.draw()

        time.sleep(0.3) # チャタリング防止
    last_key = key
    time.sleep(0.05)

