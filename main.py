import machine
import time
import framebuf
import epaper_driver  # 2.7inch V2 driver

# Waveshare Pico-ePaper-2.7 V2 landscape logical size
SCREEN_W = 264
SCREEN_H = 176

# ==========================================
# 1. キーパッド設定 (GPIO 0-7)
# ==========================================
# Row(行)を出力、Col(列)を入力(Pull-down)に設定
ROW_PINS = [0, 1, 2, 3]

# Columns. If 4/5/6/0 do not react, the second column line is the issue.
# Default wiring is GP4, GP5, GP6, GP7.
# To avoid a bad/noisy GP5 line, move that keypad wire from GP5 to GP14 and
# change this to: COL_PINS = [4, 14, 6, 7]
COL_PINS = [4, 5, 6, 7]

rows = [machine.Pin(i, machine.Pin.OUT, value=0) for i in ROW_PINS]
cols = [machine.Pin(i, machine.Pin.IN, machine.Pin.PULL_DOWN) for i in COL_PINS]
print("keypad rows GP{} cols GP{}".format(ROW_PINS, COL_PINS))
if COL_PINS[1] == 5:
    print("If keys 4/5/6/0 fail, move keypad column-2 from GP5 to GP14 and set COL_PINS=[4,14,6,7]")

KEY_MAP = [
    ["1", "4", "7", "10"],  # A=10pt / 設定画面では Start
    ["2", "5", "8", "11"],  # B=11pt
    ["3", "6", "9", "12"],  # C=12pt
    ["U", "0", "R", "B"],   # U=Undo, 0=Miss, R=Reset, B=Burst(25)
]

is_drawing = False


def keypad_sleep():
    # 描画中の電流/ノイズ干渉を避けるため、GPIO0-7を一時的に高インピーダンス化。
    for p in rows + cols:
        p.init(mode=machine.Pin.IN)


def keypad_wake():
    # キーパッドスキャン用のGPIO設定に戻す。
    for p in rows:
        p.init(mode=machine.Pin.OUT, value=0)
    for p in cols:
        p.init(mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)


def scan_keypad():
    if is_drawing:
        return None

    # Normal scan: drive rows, read columns.
    for row_pin in rows:
        row_pin.value(0)

    for r_idx, row_pin in enumerate(rows):
        row_pin.value(1)
        # Give the matrix line time to settle.  This helps with the e-paper HAT
        # and longer keypad wiring.
        time.sleep_ms(1)
        for c_idx, col_pin in enumerate(cols):
            if col_pin.value() == 1:
                row_pin.value(0)
                key = KEY_MAP[r_idx][c_idx]
                print("key is {} row={} GP{} col={} GP{} normal".format(
                    key, r_idx, ROW_PINS[r_idx], c_idx, COL_PINS[c_idx]
                ))
                return key
        row_pin.value(0)

    # Fallback scan: drive columns, read rows.
    # If one column input (notably GP5 for 4/5/6/0) is weak or not read reliably,
    # this can still detect the key by reading the row side instead.
    for p in rows + cols:
        p.init(mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)
    for c_idx, col_pin in enumerate(cols):
        col_pin.init(mode=machine.Pin.OUT, value=1)
        time.sleep_ms(1)
        for r_idx, row_pin in enumerate(rows):
            if row_pin.value() == 1:
                col_pin.value(0)
                keypad_wake()
                key = KEY_MAP[r_idx][c_idx]
                print("key is {} row={} GP{} col={} GP{} reverse".format(
                    key, r_idx, ROW_PINS[r_idx], c_idx, COL_PINS[c_idx]
                ))
                return key
        col_pin.value(0)
        col_pin.init(mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)

    keypad_wake()
    return None


# ==========================================
# 2. ゲーム管理クラス
# ==========================================
class MolkkyGame:
    def __init__(self):
        self.epd = epaper_driver.EPD_2in7_V2_Landscape()
        self.epd.Clear()
        self.state = 0  # 0:設定, 1:試合中
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None  # 1手前のみ保存
        self.msg = "Welcome!"
        self.turn_count = 1

    def draw_scaled_text(self, text, x, y, scale=4, color=0):
        text = str(text)
        src_w = max(1, len(text) * 8)
        src_h = 8
        src = bytearray(src_w * src_h // 8)
        fb = framebuf.FrameBuffer(src, src_w, src_h, framebuf.MONO_VLSB)
        fb.fill(0)
        fb.text(text, 0, 0, 1)
        for py in range(src_h):
            for px in range(src_w):
                if fb.pixel(px, py):
                    self.epd.fill_rect(x + px * scale, y + py * scale, scale, scale, color)

    def draw_scaled_center(self, text, y, scale=4, color=0):
        text = str(text)
        w = len(text) * 8 * scale
        x = max(0, (SCREEN_W - w) // 2)
        self.draw_scaled_text(text, x, y, scale, color)

    def draw(self):
        self.epd.fill(0xff)  # 白

        if self.state == 0:
            self.epd.text("MOLKKY SCOREBOARD", 10, 10, 0)
            self.epd.text("Players: [{}]".format(self.num_players), 10, 40, 0)
            self.epd.text("1-4:Set Num", 10, 70, 0)
            self.epd.text("A/10:Start", 10, 88, 0)
            self.epd.text("Game: 1-12=Score", 10, 124, 0)
            self.epd.text("0=Miss U=Undo R=Reset B=25", 10, 142, 0)
        else:
            self.epd.fill_rect(0, 0, SCREEN_W, 18, 0)  # 黒ヘッダー
            self.epd.text("Turn:{}".format(self.turn_count), 10, 5, 0xff)

            # プレイヤーリスト表示。各プレイヤーの点数を大きく表示し、
            # 現在の投擲者は点数だけ白黒反転で示す。
            for i, pl in enumerate(self.players):
                x = 10 if i < 2 else 140
                y = 26 + (i % 2) * 55
                current = i == self.cur_idx

                self.epd.text("{}:".format(pl["name"]), x, y, 0)
                score_text = "OUT" if pl["out"] else str(pl["score"])
                scale = 3 if len(score_text) <= 2 else 2
                score_x = x + 28
                score_y = y + 10
                score_w = len(score_text) * 8 * scale
                score_h = 8 * scale
                if current:
                    self.epd.fill_rect(score_x - 4, score_y - 3, score_w + 8, score_h + 6, 0)
                    self.draw_scaled_text(score_text, score_x, score_y, scale, 0xff)
                else:
                    self.draw_scaled_text(score_text, score_x, score_y, scale, 0)

                miss = "X" * pl["miss"]
                if miss == "":
                    miss = "-"
                self.epd.text("M:{} S:{}".format(miss, pl["sets"]), x, y + 39, 0)

            self.epd.text(self.msg, 10, 134, 0)
            self.epd.text("1-12 score 0 miss U undo", 10, 150, 0)
            self.epd.text("R reset B burst(25)", 10, 164, 0)

        self.epd.display()

    def redraw(self, force_refresh=False):
        update_display_safe(self, force_refresh)

    def start_game(self):
        self.players = [
            {"name": "P{}".format(i + 1), "score": 0, "miss": 0, "sets": 0, "out": False}
            for i in range(self.num_players)
        ]
        self.state = 1
        self.cur_idx = 0
        self.turn_count = 1
        self.msg = "Game Start!"
        self.redraw()

    def update_score(self, s):
        # Undo用に現状をコピー（簡易版）
        self.history = {
            "players": [dict(p) for p in self.players],
            "cur_idx": self.cur_idx,
            "msg": self.msg,
            "turn_count": self.turn_count,
        }

        p = self.players[self.cur_idx]
        set_finished = False
        if s == 0:
            p["miss"] += 1
            if p["miss"] >= 3:
                p["out"] = True
                self.msg = "{} is OUT!".format(p["name"])
            else:
                self.msg = "{} Miss".format(p["name"])
        else:
            p["miss"] = 0
            p["score"] += s
            if p["score"] == 50:
                p["sets"] += 1
                self.msg = "{} Win Set!".format(p["name"])
                set_finished = True
                self.reset_scores()  # 全員0点に戻して次のセットへ
            elif p["score"] > 50:
                p["score"] = 25
                self.msg = "Over 50! Back to 25"
            else:
                self.msg = "{} +{}".format(p["name"], s)

        prev_idx = self.cur_idx
        self.next_turn()
        # Turn count advances only after all players have thrown once.
        turn_advanced = self.cur_idx <= prev_idx
        if turn_advanced:
            self.turn_count += 1
        force_refresh = set_finished or (turn_advanced and self.turn_count % 5 == 0)
        self.redraw(force_refresh)

    def undo(self):
        if self.history:
            self.players = self.history["players"]
            self.cur_idx = self.history["cur_idx"]
            self.turn_count = self.history.get("turn_count", self.turn_count)
            self.msg = "Undo!"
            self.history = None
            self.redraw()

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


def update_display_safe(game, force_refresh=False):
    global is_drawing
    is_drawing = True
    keypad_sleep()
    try:
        if force_refresh:
            print("EPD forced refresh")
            game.epd.Clear()
        game.draw()
    finally:
        keypad_wake()
        is_drawing = False


# ==========================================
# 3. メインループ
# ==========================================
keypad_wake()
game = MolkkyGame()
update_display_safe(game)

last_key = None
while True:
    key = scan_keypad()
    if key and key != last_key:
        if game.state == 0:
            if key in ["1", "2", "3", "4"]:
                game.num_players = int(key)
                game.redraw()
            elif key == "10":  # Aボタンで開始
                game.start_game()

        elif game.state == 1:
            if key == "0":  # Miss
                game.update_score(0)
            elif key in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]:
                game.update_score(int(key))
            elif key == "B":  # Burst
                game.history = {
                    "players": [dict(p) for p in game.players],
                    "cur_idx": game.cur_idx,
                    "msg": game.msg,
                    "turn_count": game.turn_count,
                }
                game.players[game.cur_idx]["score"] = 25
                game.msg = "Forced 25"
                prev_idx = game.cur_idx
                game.next_turn()
                turn_advanced = game.cur_idx <= prev_idx
                if turn_advanced:
                    game.turn_count += 1
                force_refresh = turn_advanced and game.turn_count % 5 == 0
                game.redraw(force_refresh)
            elif key == "U":  # Undo
                game.undo()
            elif key == "R":  # 全リセット
                game.state = 0
                game.turn_count = 1
                game.redraw(True)

        time.sleep(0.3)  # チャタリング防止
    last_key = key
    time.sleep(0.05)
