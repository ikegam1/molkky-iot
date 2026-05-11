import machine
import time
import epaper_driver  # 2.7inch V2 driver

# Waveshare Pico-ePaper-2.7 V2 landscape logical size
SCREEN_W = 264
SCREEN_H = 176

# ==========================================
# 1. キーパッド設定 (GPIO 0-7)
# ==========================================
# Row(行)を出力、Col(列)を入力(Pull-down)に設定
rows = [machine.Pin(i, machine.Pin.OUT) for i in range(4)]
cols = [machine.Pin(i, machine.Pin.IN, machine.Pin.PULL_DOWN) for i in range(4, 8)]

KEY_MAP = [
    ["1", "2", "3", "10"],  # A=10pt / 設定画面では Start
    ["4", "5", "6", "11"],  # B=11pt
    ["7", "8", "9", "12"],  # C=12pt
    ["U", "0", "R", "B"],   # U=Undo, 0=Miss, R=Reset, B=Burst(25)
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
        # Landscapeモード(横向き)を使用
        # 互換aliasもありますが、2.7inch V2用クラスを明示します。
        self.epd = epaper_driver.EPD_2in7_V2_Landscape()
        self.epd.Clear()
        self.state = 0  # 0:設定, 1:試合中
        self.num_players = 2
        self.players = []
        self.cur_idx = 0
        self.history = None  # 1手前のみ保存
        self.msg = "Welcome!"

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
            p = self.players[self.cur_idx]
            self.epd.fill_rect(0, 0, SCREEN_W, 18, 0)  # 黒ヘッダー
            self.epd.text("Turn: {}".format(p["name"]), 10, 5, 0xff)

            # プレイヤーリスト表示
            for i, pl in enumerate(self.players):
                x = 10 if i < 2 else 140
                y = 30 + (i % 2) * 45
                mark = ">" if i == self.cur_idx else " "
                status = "OUT" if pl["out"] else "{}pt".format(pl["score"])
                self.epd.text("{}{}: {}".format(mark, pl["name"], status), x, y, 0)
                miss = "X" * pl["miss"]
                if miss == "":
                    miss = "-"
                self.epd.text(" M:{} S:{}".format(miss, pl["sets"]), x, y + 15, 0)

            self.epd.text(self.msg, 10, 125, 0)
            self.epd.text("1-12 score 0 miss U undo", 10, 145, 0)
            self.epd.text("R reset B burst(25)", 10, 160, 0)

        self.epd.display()

    def start_game(self):
        self.players = [
            {"name": "P{}".format(i + 1), "score": 0, "miss": 0, "sets": 0, "out": False}
            for i in range(self.num_players)
        ]
        self.state = 1
        self.cur_idx = 0
        self.msg = "Game Start!"
        self.draw()

    def update_score(self, s):
        # Undo用に現状をコピー（簡易版）
        self.history = {"players": [dict(p) for p in self.players], "cur_idx": self.cur_idx, "msg": self.msg}

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
            elif key == "10":  # Aボタンで開始
                game.start_game()

        elif game.state == 1:
            if key.isdigit() or key in ["10", "11", "12"]:
                game.update_score(int(key))
            elif key == "B":  # Burst
                game.history = {"players": [dict(p) for p in game.players], "cur_idx": game.cur_idx, "msg": game.msg}
                game.players[game.cur_idx]["score"] = 25
                game.msg = "Forced 25pt"
                game.next_turn()
                game.draw()
            elif key == "U":  # Undo
                game.undo()
            elif key == "R":  # 全リセット
                game.state = 0
                game.draw()

        time.sleep(0.3)  # チャタリング防止
    last_key = key
    time.sleep(0.05)
