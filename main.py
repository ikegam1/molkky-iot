import machine
import time
import epaper_driver # 先ほど成功したドライバをインポート

# 2.13 inch e-paper を横向きで使う時の論理サイズ
SCREEN_W = 250
SCREEN_H = 122
SAFE_X = 4
SAFE_Y = 4
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
        self.state = 0 # 0:設定, 1:試合中, 2:表示診断
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None # 1手前のみ保存
        self.msg = "Welcome!"
        
        # 4. 初期メニューの描画
        # self.draw()

    def text_width(self, text):
        return len(str(text)) * FONT_W

    def draw_text_center(self, text, y, color=0):
        self.draw_text_center_in(text, SAFE_X, SCREEN_W - SAFE_X * 2, y, color)

    def draw_text_center_in(self, text, x, w, y, color=0):
        text = str(text)
        tx = x + max(0, (w - self.text_width(text)) // 2)
        self.epd.text(text, tx, y, color)

    def draw_text_fit(self, text, x, y, max_w, color=0):
        text = str(text)
        max_chars = max_w // FONT_W
        if len(text) > max_chars:
            text = text[:max(0, max_chars - 1)] + "."
        self.epd.text(text, x, y, color)

    DIGITS = {
        "0": ("111", "101", "101", "101", "111"),
        "1": ("010", "110", "010", "010", "111"),
        "2": ("111", "001", "111", "100", "111"),
        "3": ("111", "001", "111", "001", "111"),
        "4": ("101", "101", "111", "001", "001"),
        "5": ("111", "100", "111", "001", "111"),
        "6": ("111", "100", "111", "101", "111"),
        "7": ("111", "001", "010", "010", "010"),
        "8": ("111", "101", "111", "101", "111"),
        "9": ("111", "101", "111", "001", "111"),
    }

    def big_number_width(self, text, unit):
        text = str(text)
        if not text:
            return 0
        return len(text) * 3 * unit + (len(text) - 1) * unit

    def draw_big_number(self, text, x, y, unit=5, color=0):
        # framebuf.text の拡大は崩れやすいので、点数はブロック数字で描く。
        text = str(text)
        cx = x
        for ch in text:
            pattern = self.DIGITS.get(ch)
            if not pattern:
                cx += 4 * unit
                continue
            for row, line in enumerate(pattern):
                for col, bit in enumerate(line):
                    if bit == "1":
                        self.epd.fill_rect(cx + col * unit, y + row * unit, unit, unit, color)
            cx += 4 * unit

    def draw_big_number_center_in(self, text, x, w, y, unit=5, color=0):
        text = str(text)
        tx = x + max(0, (w - self.big_number_width(text, unit)) // 2)
        self.draw_big_number(text, tx, y, unit, color)

    def draw_player_score(self, pl, x, y, w, unit):
        # 右下ほど崩れやすい実機状態なので、情報量を絞って大きく描く。
        # 横長の黒帯や反転小文字は崩れが目立つため使わない。
        current = pl == self.players[self.cur_idx]
        if current:
            self.epd.fill_rect(x, y + 2, 10, 10, 0)
        self.epd.text(pl["name"], x + 16, y + 2, 0)

        if pl["out"]:
            self.epd.text("OUT", x + 28, y + 28, 0)
        else:
            self.draw_big_number_center_in(pl["score"], x, w, y + 16, unit, 0)

    def draw(self):
        self.epd.fill(0xff) # 白
        
        if self.state == 0:
            # 小さい文字を減らし、左上〜中央に大きく表示する。
            self.epd.text("MOLKKY", SAFE_X + 8, SAFE_Y + 8, 0)
            self.epd.text("PLAYERS", SAFE_X + 8, SAFE_Y + 26, 0)
            self.draw_big_number(str(self.num_players), SAFE_X + 86, SAFE_Y + 40, 10, 0)
            self.epd.text("1-4:SET", SAFE_X + 8, SAFE_Y + 90, 0)
            self.epd.text("A:START", SAFE_X + 88, SAFE_Y + 90, 0)
            self.epd.text("D:TEST", SAFE_X + 8, SAFE_Y + 106, 0)
        elif self.state == 1:
            p = self.players[self.cur_idx]

            if self.num_players <= 2:
                # 2人分を左〜中央に縦積みする。右端と細い文字は使わない。
                self.draw_player_score(self.players[0], SAFE_X + 10, SAFE_Y + 6, 150, 7)
                if len(self.players) > 1:
                    self.draw_player_score(self.players[1], SAFE_X + 10, SAFE_Y + 62, 150, 7)
            else:
                # 3-4人は現在プレイヤーだけを大きく表示する。
                self.draw_player_score(p, SAFE_X + 16, SAFE_Y + 24, 150, 9)
        elif self.state == 2:
            self.draw_diagnostics()

        self.epd.display()

    def draw_diagnostics(self):
        # 表示RAM/座標のズレ確認用。B(D)で表示、Rで戻る。
        # 右下に行くほど崩れる場合、縦線・横線の曲がり方で転送方向を判断する。
        self.epd.text("TEST", SAFE_X + 4, SAFE_Y + 4, 0)
        self.epd.fill_rect(SAFE_X + 4, SAFE_Y + 18, 180, 3, 0)
        self.epd.fill_rect(SAFE_X + 4, SAFE_Y + 18, 3, 86, 0)
        self.epd.fill_rect(SAFE_X + 44, SAFE_Y + 18, 3, 86, 0)
        self.epd.fill_rect(SAFE_X + 84, SAFE_Y + 18, 3, 86, 0)
        self.epd.fill_rect(SAFE_X + 124, SAFE_Y + 18, 3, 86, 0)
        self.epd.fill_rect(SAFE_X + 164, SAFE_Y + 18, 3, 86, 0)
        self.epd.fill_rect(SAFE_X + 4, SAFE_Y + 44, 180, 3, 0)
        self.epd.fill_rect(SAFE_X + 4, SAFE_Y + 70, 180, 3, 0)
        self.epd.fill_rect(SAFE_X + 4, SAFE_Y + 96, 180, 3, 0)
        self.epd.text("0", SAFE_X + 8, SAFE_Y + 24, 0xff)
        self.epd.text("40", SAFE_X + 48, SAFE_Y + 24, 0xff)
        self.epd.text("80", SAFE_X + 88, SAFE_Y + 24, 0xff)
        self.epd.text("120", SAFE_X + 128, SAFE_Y + 24, 0xff)

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
            elif key == "B": # Dボタンで表示診断
                game.state = 2
                game.draw()
        
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

        elif game.state == 2:
            if key == "R": # 診断終了
                game.state = 0
                game.draw()

        time.sleep(0.3) # チャタリング防止
    last_key = key
    time.sleep(0.05)

