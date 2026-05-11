import machine
import time
import framebuf
import epaper_driver

# Waveshare Pico-ePaper-2.7 V2 landscape logical size
SCREEN_W = 264
SCREEN_H = 176
FONT_W = 8
FONT_H = 8

# ==========================================
# 1. Keypad settings (GPIO 0-7)
# ==========================================
# Rows are output, columns are input with pull-down.
rows = [machine.Pin(i, machine.Pin.OUT) for i in range(4)]
cols = [machine.Pin(i, machine.Pin.IN, machine.Pin.PULL_DOWN) for i in range(4, 8)]

KEY_MAP = [
    ["1", "4", "7", "10"],  # A = 10pt / Start on setup screen
    ["2", "5", "8", "11"],  # B = 11pt
    ["3", "6", "9", "12"],  # C = 12pt
    ["U", "0", "R", "B"],   # D row: Undo, Miss(0), Reset, Burst(25)
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
# 2. Game class
# ==========================================
class MolkkyGame:
    def __init__(self):
        self.epd = epaper_driver.EPD_2in7_V2_Landscape()
        self.epd.Clear()
        self.state = 0  # 0: setup, 1: playing
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None
        self.msg = "Welcome!"

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
        # framebuf.text is fixed 8x8, so draw to a temporary buffer and scale it.
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

    def draw_header(self, title):
        self.epd.fill_rect(0, 0, SCREEN_W, 18, 0)
        self.draw_text_center(title, 5, 0xFF)

    def draw_setup(self):
        self.draw_text_center("MOLKKY", 12, 0, 3)
        self.draw_text_center("SCOREBOARD", 42, 0, 2)
        self.draw_text_center("Players: [{}]".format(self.num_players), 72, 0)

        self.epd.hline(18, 92, SCREEN_W - 36, 0)
        self.draw_text_center("1-4 : Set players", 102, 0)
        self.draw_text_center("A/10: Start game", 118, 0)
        self.draw_text_center("During game: 1-12 score", 138, 0)
        self.draw_text_center("0 miss  U undo  R reset  B burst", 154, 0)

    def draw_scoreboard(self):
        p = self.players[self.cur_idx]
        self.draw_header("Turn: {}".format(p["name"]))

        score_text = "OUT" if p["out"] else str(p["score"])
        scale = 5 if len(score_text) <= 2 else 3
        self.draw_text_center(score_text, 30, 0, scale)
        if not p["out"]:
            self.draw_text_center("POINTS", 72, 0)
        self.draw_text_center(self.msg, 90, 0)

        # Bottom help line
        self.epd.hline(0, 108, SCREEN_W, 0)
        self.draw_text_center("Input: 1-12 / 0=miss / U=undo", 114, 0)

        # Player summary, up to 4 players in two columns.
        for i, pl in enumerate(self.players):
            x = 4 if i < 2 else 136
            y = 132 + (i % 2) * 18
            mark = ">" if i == self.cur_idx else " "
            status = "OUT" if pl["out"] else "{}pt".format(pl["score"])
            miss = "X" * pl["miss"] or "-"
            line = "{}{} {} M:{} S:{}".format(mark, pl["name"], status, miss, pl["sets"])
            self.draw_text_fit(line, x, y, 124, 0)

    def draw(self):
        self.epd.fill(0xFF)
        if self.state == 0:
            self.draw_setup()
        else:
            self.draw_scoreboard()
        self.epd.display()

    def start_game(self):
        self.players = [
            {"name": "P{}".format(i + 1), "score": 0, "miss": 0, "sets": 0, "out": False}
            for i in range(self.num_players)
        ]
        self.state = 1
        self.cur_idx = 0
        self.history = None
        self.msg = "Game Start!"
        self.draw()

    def update_score(self, s):
        self.history = {"players": [dict(p) for p in self.players], "cur_idx": self.cur_idx, "msg": self.msg}
        p = self.players[self.cur_idx]
        if s == 0:
            p["miss"] += 1
            if p["miss"] >= 3:
                p["out"] = True
                self.msg = "{} is OUT!".format(p["name"])
            else:
                self.msg = "{} miss".format(p["name"])
        else:
            p["miss"] = 0
            p["score"] += s
            if p["score"] == 50:
                p["sets"] += 1
                self.msg = "{} Win Set!".format(p["name"])
                self.reset_scores()
            elif p["score"] > 50:
                p["score"] = 25
                self.msg = "Over 50! Back to 25"
            else:
                self.msg = "{} +{}pt".format(p["name"], s)
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
# 3. Main loop
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
            elif key == "10":
                game.start_game()
        elif game.state == 1:
            if key.isdigit() or key in ["10", "11", "12"]:
                game.update_score(int(key))
            elif key == "B":
                game.history = {"players": [dict(p) for p in game.players], "cur_idx": game.cur_idx, "msg": game.msg}
                game.players[game.cur_idx]["score"] = 25
                game.msg = "Forced 25pt"
                game.next_turn()
                game.draw()
            elif key == "U":
                game.undo()
            elif key == "R":
                game.state = 0
                game.msg = "Reset"
                game.draw()
        time.sleep(0.3)
    last_key = key
    time.sleep(0.05)
