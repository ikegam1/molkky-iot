import machine
import time
import epaper_driver

try:
    led = machine.Pin("LED", machine.Pin.OUT)
except Exception:
    led = machine.Pin(25, machine.Pin.OUT)
led.value(1)
print("molkky-iot boot")

# Rect-only UI.
# The panel renders fill_rect blocks well, while text/thin lines skew badly.
SCREEN_W = 264
SCREEN_H = 176
SAFE_X = 8
SAFE_Y = 8

rows = [machine.Pin(i, machine.Pin.OUT) for i in range(4)]
cols = [machine.Pin(i, machine.Pin.IN, machine.Pin.PULL_DOWN) for i in range(4, 8)]

KEY_MAP = [
    ["1", "4", "7", "10"],
    ["2", "5", "8", "11"],
    ["3", "6", "9", "12"],
    ["U", "0", "R", "B"]
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

    # Tiny 3x5 block letters used only for P / S / E / T / O / U.
    LETTERS = {
        "P": ("110", "101", "110", "100", "100"),
        "S": ("111", "100", "111", "001", "111"),
        "E": ("111", "100", "110", "100", "111"),
        "T": ("111", "010", "010", "010", "010"),
        "O": ("111", "101", "101", "101", "111"),
        "U": ("101", "101", "101", "101", "111"),
    }

    def __init__(self):
        self.epd = epaper_driver.EPD_2in7_V2_Landscape()
        self.epd.Clear()
        self.state = 0
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None

    def draw_pattern(self, pattern, x, y, unit, color=0):
        for row, line in enumerate(pattern):
            for col, bit in enumerate(line):
                if bit == "1":
                    self.epd.fill_rect(x + col * unit, y + row * unit, unit, unit, color)

    def block_width(self, text, unit):
        return len(str(text)) * 3 * unit + max(0, len(str(text)) - 1) * unit

    def draw_number(self, value, x, y, unit):
        cx = x
        for ch in str(value):
            self.draw_pattern(self.DIGITS.get(ch, self.DIGITS["0"]), cx, y, unit)
            cx += 4 * unit

    def draw_number_center(self, value, y, unit, x0=0, width=SCREEN_W):
        x = max(x0 + SAFE_X, x0 + (width - self.block_width(value, unit)) // 2)
        self.draw_number(value, x, y, unit)

    def draw_letters(self, text, x, y, unit):
        cx = x
        for ch in text:
            if ch in self.LETTERS:
                self.draw_pattern(self.LETTERS[ch], cx, y, unit)
            cx += 4 * unit

    def draw_player(self, index, x, y, width):
        pl = self.players[index]
        # Current player marker: solid block on the left.
        if index == self.cur_idx:
            self.epd.fill_rect(x + SAFE_X, y + 6, 10, 18, 0)
        self.draw_letters("P", x + SAFE_X + 18, y, 4)
        self.draw_number(index + 1, x + SAFE_X + 36, y, 4)
        if pl["out"]:
            self.draw_letters("OUT", x + SAFE_X + 18, y + 34, 5)
        else:
            self.draw_number_center(pl["score"], y + 42, 9, x, width)

    def draw_setup(self):
        # SET + large player count. No text(), only block letters/numbers.
        self.draw_letters("SET", SAFE_X + 18, 18, 5)
        self.draw_number_center(self.num_players, 58, 13)
        # Four small bottom blocks means: press 1-4 to select players.
        for i in range(4):
            self.epd.fill_rect(SAFE_X + 36 + i * 42, 134, 20, 20, 0)
        # Start hint: one wide block near bottom means A/start.
        self.epd.fill_rect(SAFE_X + 72, 158, 110, 10, 0)

    def draw(self):
        self.epd.fill(0xff)
        if self.state == 0:
            self.draw_setup()
        else:
            if self.num_players <= 2:
                self.draw_player(0, 0, 28, SCREEN_W // 2)
                if len(self.players) > 1:
                    self.draw_player(1, SCREEN_W // 2, 28, SCREEN_W // 2)
            else:
                self.draw_player(self.cur_idx, 50, 42, 164)
        self.epd.display()

    def start_game(self):
        self.players = [{"score": 0, "miss": 0, "sets": 0, "out": False} for _ in range(self.num_players)]
        self.state = 1
        self.cur_idx = 0
        self.history = None
        self.draw()

    def update_score(self, s):
        self.history = {"players": [dict(p) for p in self.players], "cur_idx": self.cur_idx}
        p = self.players[self.cur_idx]
        if s == 0:
            p["miss"] += 1
            if p["miss"] >= 3:
                p["out"] = True
        else:
            p["miss"] = 0
            p["score"] += s
            if p["score"] == 50:
                p["sets"] += 1
                self.reset_scores()
            elif p["score"] > 50:
                p["score"] = 25
        self.next_turn()
        self.draw()

    def undo(self):
        if self.history:
            self.players = self.history["players"]
            self.cur_idx = self.history["cur_idx"]
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


print("creating game")
game = MolkkyGame()
print("drawing initial screen")
game.draw()
led.value(0)
print("ready")

last_key = None
while True:
    key = scan_keypad()
    if key and key != last_key:
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
                game.players[game.cur_idx]["score"] = 25
                game.next_turn()
                game.draw()
            elif key == "U":
                game.undo()
            elif key == "R":
                game.state = 0
                game.draw()
        time.sleep(0.3)
    last_key = key
    time.sleep(0.05)
