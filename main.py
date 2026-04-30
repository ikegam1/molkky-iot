import machine
import time
import framebuf
import epaper_driver # 先ほど成功したドライバをインポート

# 2.13 inch e-paper を横向きで使う時の論理サイズ
SCREEN_W = 250
SCREEN_H = 122
FONT_W = 8
FONT_H = 8

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
        # ドライバの初期化（この時点で epd.init() が走ります）
        self.epd = epaper_driver.EPD_2in13_V4_Landscape()
        
        # 画面の物理リフレッシュ（真っ白にする）
        print("Refreshing screen...")
        self.epd.Clear() 
        self.state = 0 # 0:設定, 1:試合中
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None # 1手前のみ保存
        self.msg = "Welcome!"
        
        # 4. 初期メニューの描画
        # self.draw()

    def text_width(self, text, scale=1):
        return len(str(text)) * FONT_W * scale

    def draw_text_center(self, text, y, color=0, scale=1):
        text = str(text)
        x = max(0, (SCREEN_W - self.text_width(text, scale)) // 2)
        if scale == 1:
            self.epd.text(text, x, y, color)
        else:
            self.draw_scaled_text(text, x, y, scale, color)

    def draw_text_fit(self, text, x, y, max_w, color=0):
        text = str(text)
        max_chars = max_w // FONT_W
        if len(text) > max_chars:
            text = text[:max(0, max_chars - 1)] + "."
        self.epd.text(text, x, y, color)

    def draw_scaled_text(self, text, x, y, scale=2, color=0):
        # framebuf.text は 8x8 固定なので、一時バッファに描いて拡大コピーする。
        text = str(text)
        src_w = max(1, len(text) * FONT_W)
        src_h = FONT_H
        src = bytearray(src_w * src_h // 8)
        fb = framebuf.FrameBuffer(src, src_w, src_h, framebuf.MONO_VLSB)
        fb.fill(0)
        fb.text(text, 0, 0, 1)
        for py in range(src_h):
            for px in range(src_w):
                if fb.pixel(px, py):
                    self.epd.fill_rect(x + px * scale, y + py * scale, scale, scale, color)

    def draw(self):
        self.epd.fill(0xff) # 白
        
        if self.state == 0:
            self.draw_text_center("MOLKKY", 8, 0, 3)
            self.draw_text_center("SCOREBOARD", 38, 0, 2)
            self.draw_text_center(f"Players: [{self.num_players}]", 68, 0)
            self.draw_text_center("1-4:Set Num", 90, 0)
            self.draw_text_center("A:Start", 106, 0)
        else:
            p = self.players[self.cur_idx]
            self.epd.fill_rect(0, 0, SCREEN_W, 17, 0) # 黒ヘッダー
            self.draw_text_center(f"Turn: {p['name']}", 5, 0xff)

            # 現在プレイヤーの点数を大きく中央表示
            score_text = "OUT" if p["out"] else str(p["score"])
            scale = 4 if len(score_text) <= 2 else 3
            self.draw_text_center(score_text, 24, 0, scale)
            self.draw_text_center("POINTS" if not p["out"] else "", 58, 0)
            self.draw_text_center(self.msg, 106, 0)
            
            # プレイヤーリスト表示（左右2列に収める）
            for i, pl in enumerate(self.players):
                x = 2 if i < 2 else 128
                y = 76 + (i % 2) * 15
                mark = ">" if i == self.cur_idx else " "
                status = "OUT" if pl["out"] else f"{pl['score']}pt"
                miss = "X" * pl["miss"] or "-"
                line = f"{mark}{pl['name']} {status} M:{miss} S:{pl['sets']}"
                self.draw_text_fit(line, x, y, 120, 0)

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

