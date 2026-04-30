import machine
import time
import epaper_driver

# Native portrait layout for Waveshare Pico-ePaper 2.13 V4.
# The controller RAM is 128x250; the visible panel is 122x250.
SCREEN_W = 122
SCREEN_H = 250
SAFE_X = 4
SAFE_Y = 4
FONT_W = 8

# ==========================================
# 1. キーパッド設定 (GPIO 0-7)
# ==========================================
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

    def __init__(self):
        self.epd = epaper_driver.EPD_2in13_V4_Landscape()
        print("Refreshing screen...")
        self.epd.Clear()
        self.state = 0 # 0:設定, 1:試合中
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None
        self.msg = "Welcome!"

    def text_width(self, text):
        return len(str(text)) * FONT_W

    def draw_text_center(self, text, y, color=0):
        text = str(text)
        x = SAFE_X + max(0, (SCREEN_W - SAFE_X * 2 - self.text_width(text)) // 2)
        self.epd.text(text, x, y, color)

    def big_number_width(self, text, unit):
        text = str(text)
        if not text:
            return 0
        return len(text) * 3 * unit + (len(text) - 1) * unit

    def draw_big_number(self, text, x, y, unit=6, color=0):
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

    def draw_big_number_center(self, text, y, unit=8, color=0):
        text = str(text)
        x = SAFE_X + max(0, (SCREEN_W - SAFE_X * 2 - self.big_number_width(text, unit)) // 2)
        self.draw_big_number(text, x, y, unit, color)

    def draw_player_score(self, pl, y):
        current = pl == self.players[self.cur_idx]
        if current:
            self.epd.fill_rect(SAFE_X + 2, y + 2, 10, 10, 0)
        self.epd.text(pl["name"], SAFE_X + 18, y + 2, 0)
        if pl["out"]:
            self.draw_text_center("OUT", y + 30, 0)
        else:
            self.draw_big_number_center(pl["score"], y + 18, 8, 0)

    def draw(self):
        self.epd.fill(0xff)

        if self.state == 0:
            self.draw_text_center("MOLKKY", 12, 0)
            self.draw_text_center("PLAYERS", 34, 0)
            self.draw_big_number_center(self.num_players, 60, 12, 0)
            self.draw_text_center("1-4 SET", 150, 0)
            self.draw_text_center("A START", 172, 0)
        else:
            if self.num_players <= 2:
                self.draw_player_score(self.players[0], 12)
                if len(self.players) > 1:
                    self.draw_player_score(self.players[1], 116)
            else:
                self.draw_text_center("TURN", 16, 0)
                self.draw_player_score(self.players[self.cur_idx], 52)

        self.epd.display()

    def start_game(self):
        self.players = [{"name":f"P{i+1}", "score":0, "miss":0, "sets":0, "out":False} for i in range(self.num_players)]
        self.state = 1
        self.cur_idx = 0
        self.msg = "Game Start!"
        self.draw()

    def update_score(self, s):
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
                self.reset_scores()
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

        time.sleep(0.3)
    last_key = key
    time.sleep(0.05)
