import machine
import time
import epaper_driver  # 2.7inch V2 driver

# Waveshare Pico-ePaper-2.7 V2 landscape logical size
SCREEN_W = 264
SCREEN_H = 176

# ==========================================
# 1. 基板上KEY設定
# ==========================================
# Waveshare Pico-ePaper系の4キー想定:
# KEY1=GP15, KEY2=GP17, KEY3=GP2, KEY4=GP3
# もし反応するボタン順が違う場合は、この配列だけ入れ替えてください。
KEY_PINS = [15, 17, 2, 3]
LONG_PRESS_MS = 800
DEBOUNCE_MS = 40

keys = [machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP) for pin in KEY_PINS]

active_key = None
press_started_at = 0
last_event_at = 0


def scan_buttons():
    """Return (key_index, is_long) on release. key_index is 0..3."""
    global active_key, press_started_at, last_event_at
    now = time.ticks_ms()

    if time.ticks_diff(now, last_event_at) < DEBOUNCE_MS:
        return None

    pressed = None
    for i, pin in enumerate(keys):
        if pin.value() == 0:  # active low
            pressed = i
            break

    if active_key is None:
        if pressed is not None:
            active_key = pressed
            press_started_at = now
            last_event_at = now
        return None

    # Wait until the same key is released, then classify short/long.
    if pressed == active_key:
        return None

    released_key = active_key
    active_key = None
    last_event_at = now
    duration = time.ticks_diff(now, press_started_at)
    return released_key, duration >= LONG_PRESS_MS


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
        self.input_score = 0

    def draw(self):
        self.epd.fill(0xff)  # 白

        if self.state == 0:
            self.epd.text("MOLKKY SCOREBOARD", 10, 10, 0)
            self.epd.text("Players: [{}]".format(self.num_players), 10, 40, 0)
            self.epd.text("KEY1:+1   KEY2:-1", 10, 75, 0)
            self.epd.text("KEY3:Start", 10, 93, 0)
            self.epd.text("KEY4 long:Reset", 10, 111, 0)
            self.epd.text("During game:", 10, 140, 0)
            self.epd.text("K1/K2 score K3 OK K4 Undo", 10, 158, 0)
        else:
            p = self.players[self.cur_idx]
            self.epd.fill_rect(0, 0, SCREEN_W, 18, 0)  # 黒ヘッダー
            self.epd.text("Turn: {}".format(p["name"]), 10, 5, 0xff)

            self.epd.text("Input: [{}]".format(self.input_score), 10, 25, 0)
            self.epd.text("K1 +1/+10  K2 -1/-10", 10, 43, 0)
            self.epd.text("K3 OK / long=0pt", 10, 61, 0)
            self.epd.text("K4 Undo / long=Reset", 10, 79, 0)

            # プレイヤーリスト表示
            for i, pl in enumerate(self.players):
                x = 10 if i < 2 else 140
                y = 104 + (i % 2) * 30
                mark = ">" if i == self.cur_idx else " "
                status = "OUT" if pl["out"] else "{}pt".format(pl["score"])
                self.epd.text("{}{}: {}".format(mark, pl["name"], status), x, y, 0)
                miss = "X" * pl["miss"]
                if miss == "":
                    miss = "-"
                self.epd.text(" M:{} S:{}".format(miss, pl["sets"]), x, y + 15, 0)

            self.epd.text(self.msg, 10, 164, 0)

        self.epd.display()

    def change_players(self, delta):
        self.num_players += delta
        if self.num_players < 1:
            self.num_players = 1
        if self.num_players > 4:
            self.num_players = 4
        self.msg = "Players: {}".format(self.num_players)
        self.draw()

    def change_input_score(self, delta):
        self.input_score += delta
        if self.input_score < 0:
            self.input_score = 0
        if self.input_score > 12:
            self.input_score = 12
        self.msg = "Input {}".format(self.input_score)
        self.draw()

    def start_game(self):
        self.players = [
            {"name": "P{}".format(i + 1), "score": 0, "miss": 0, "sets": 0, "out": False}
            for i in range(self.num_players)
        ]
        self.state = 1
        self.cur_idx = 0
        self.history = None
        self.input_score = 0
        self.msg = "Game Start!"
        self.draw()

    def update_score(self, s):
        # Undo用に現状をコピー（簡易版）
        self.history = {
            "players": [dict(p) for p in self.players],
            "cur_idx": self.cur_idx,
            "msg": self.msg,
            "input_score": self.input_score,
        }

        p = self.players[self.cur_idx]
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
                self.reset_scores()  # 全員0点に戻して次のセットへ
            elif p["score"] > 50:
                p["score"] = 25
                self.msg = "Over 50! Back to 25"
            else:
                self.msg = "{} +{}pt".format(p["name"], s)

        self.input_score = 0
        self.next_turn()
        self.draw()

    def undo(self):
        if self.history:
            self.players = self.history["players"]
            self.cur_idx = self.history["cur_idx"]
            self.input_score = self.history.get("input_score", 0)
            self.msg = "Undo!"
            self.history = None
            self.draw()

    def reset_to_setup(self):
        self.state = 0
        self.players = []
        self.cur_idx = 0
        self.history = None
        self.input_score = 0
        self.msg = "Reset"
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

    def handle_button(self, key_index, is_long):
        # KEY1: +1 / long +10
        if key_index == 0:
            if self.state == 0:
                self.change_players(1 if not is_long else 2)
            else:
                self.change_input_score(10 if is_long else 1)

        # KEY2: -1 / long -10
        elif key_index == 1:
            if self.state == 0:
                self.change_players(-1 if not is_long else -2)
            else:
                self.change_input_score(-10 if is_long else -1)

        # KEY3: OK / long 0pt
        elif key_index == 2:
            if self.state == 0:
                self.start_game()
            else:
                if is_long:
                    self.update_score(0)
                else:
                    self.update_score(self.input_score)

        # KEY4: Undo / long Reset
        elif key_index == 3:
            if is_long:
                self.reset_to_setup()
            elif self.state == 1:
                self.undo()


# ==========================================
# 3. メインループ
# ==========================================
game = MolkkyGame()
game.draw()

while True:
    event = scan_buttons()
    if event:
        key_index, is_long = event
        print("KEY{} {}".format(key_index + 1, "long" if is_long else "short"))
        game.handle_button(key_index, is_long)
    time.sleep(0.02)
