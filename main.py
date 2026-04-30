import machine
import time
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

    def text_width(self, text):
        return len(str(text)) * FONT_W

    def draw_text_center(self, text, y, color=0):
        self.draw_text_center_in(text, 0, SCREEN_W, y, color)

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

    def draw_player_card(self, pl, x, y, w, h, unit):
        current = pl == self.players[self.cur_idx]
        if current:
            self.epd.fill_rect(x, y, w, 11, 0)
            self.draw_text_center_in("> " + pl["name"], x, w, y + 2, 0xff)
        else:
            self.draw_text_center_in(pl["name"], x, w, y + 2, 0)

        if pl["out"]:
            self.draw_text_center_in("OUT", x, w, y + 22, 0)
        else:
            self.draw_big_number_center_in(pl["score"], x, w, y + 16, unit, 0)

        miss = "X" * pl["miss"] or "-"
        self.draw_text_center_in(f"M:{miss} S:{pl['sets']}", x, w, y + h - 10, 0)

    def draw(self):
        self.epd.fill(0xff) # 白
        
        if self.state == 0:
            # まずは標準 8x8 フォントだけを使い、初期画面の文字崩れを避ける。
            self.draw_text_center("MOLKKY SCORE", 16, 0)
            self.draw_text_center("BOARD", 30, 0)
            self.draw_text_center(f"Players: [{self.num_players}]", 58, 0)
            self.draw_text_center("1-4: Set Num", 84, 0)
            self.draw_text_center("A: Start", 100, 0)
        else:
            p = self.players[self.cur_idx]
            self.epd.fill_rect(0, 0, SCREEN_W, 15, 0) # 黒ヘッダー
            self.draw_text_center(f"Turn: {p['name']}", 4, 0xff)
            self.draw_text_center(self.msg, 112, 0)

            # 2人対戦では両者の点数を大きく左右に表示する。
            # 3-4人では2x2グリッドに収める。
            if self.num_players <= 2:
                for i, pl in enumerate(self.players):
                    self.draw_player_card(pl, i * 125, 22, 125, 80, 6)
            else:
                for i, pl in enumerate(self.players):
                    x = 0 if i % 2 == 0 else 125
                    y = 20 if i < 2 else 66
                    self.draw_player_card(pl, x, y, 125, 42, 4)

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

