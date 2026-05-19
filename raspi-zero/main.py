import sys
import os
import time
import lgpio
from PIL import Image, ImageDraw, ImageFont
import epd2in13_V4

# ==========================================
# 1. ハードウェア設定 (キーパッド & ブザー)
# ==========================================
ROW_PINS = [26, 12, 20, 16]
COL_PINS = [5, 6, 13, 19]
BEEP_PIN = 22  # ブザー用のピン

KEY_MAP = [
    ["1", "2", "3", "U"],
    ["4", "5", "6", "O"],
    ["7", "8", "9", "R"],
    ["10", "11", "12", "B"]
]

# GPIOチップのオープン
h = lgpio.gpiochip_open(0)

def setup_hardware():
    # COLを出力、初期値HIGH
    for pin in COL_PINS:
        lgpio.gpio_claim_output(h, pin)
        lgpio.gpio_write(h, pin, 1)
    # ROWを入力、プルアップ
    for pin in ROW_PINS:
        lgpio.gpio_claim_input(h, pin, lgpio.SET_PULL_UP)
    # ブザーを出力、初期値LOW(消音)
    lgpio.gpio_claim_output(h, BEEP_PIN)
    lgpio.gpio_write(h, BEEP_PIN, 0)

def scan_keypad():
    for c_idx, c_pin in enumerate(COL_PINS):
        lgpio.gpio_write(h, c_pin, 0) # COLをLOWに落とす
        for r_idx, r_pin in enumerate(ROW_PINS):
            if lgpio.gpio_read(h, r_pin) == 0: # ROWがLOWなら押し下げ
                # チャタリング防止：離されるまで待機
                while lgpio.gpio_read(h, r_pin) == 0:
                    time.sleep(0.01)
                lgpio.gpio_write(h, c_pin, 1)
                return KEY_MAP[r_idx][c_idx]
        lgpio.gpio_write(h, c_pin, 1)
    return None

# ==========================================
# ブザー演奏関数 (長さとリズムで鳴らし分け)
# ==========================================
def play_sound(pattern):
    if pattern == "start":
        # 1. 試合開始：「ジャーン！」（長めに1回鳴らす➔0.2秒に調整）
        for _ in range(2):
            lgpio.gpio_write(h, BEEP_PIN, 1)
            time.sleep(0.4)
            lgpio.gpio_write(h, BEEP_PIN, 0)
            time.sleep(0.15)

    elif pattern == "score":
        # 2. スコア入力：短く「ピッ」（0.3秒から0.05秒に短縮）
        lgpio.gpio_write(h, BEEP_PIN, 1)
        time.sleep(0.3)
        lgpio.gpio_write(h, BEEP_PIN, 0)

    elif pattern == "miss":
        # 3. 0点入力/バースト：少し間延びした音「ピー」（0.5秒から0.2秒に短縮）
        lgpio.gpio_write(h, BEEP_PIN, 1)
        time.sleep(0.5)
        lgpio.gpio_write(h, BEEP_PIN, 0)

    elif pattern == "win":
        # 4. ゲーム勝利：「ピピッ！」（短く2回連続、テンポアップ）
        for _ in range(2):
            lgpio.gpio_write(h, BEEP_PIN, 1)
            time.sleep(0.3)
            lgpio.gpio_write(h, BEEP_PIN, 0)
            time.sleep(0.15)

    elif pattern == "out":
        # 5. 3ミスアウト：「ブブー！」（長めを2回重々しく、テンポアップ）
        for _ in range(2):
            lgpio.gpio_write(h, BEEP_PIN, 1)
            time.sleep(0.45)
            lgpio.gpio_write(h, BEEP_PIN, 0)
            time.sleep(0.16)

# ==========================================
# 2. ゲーム管理
# ==========================================
class MolkkyGame:
    def __init__(self):
        self.epd = epd2in13_V4.EPD()
        self.width = self.epd.height # 250
        self.height = self.epd.width # 122

        try:
            self.font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            self.font_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            self.font_l = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except:
            self.font_s = self.font_m = self.font_l = ImageFont.load_default()

        self.state = 0 # 0:設定, 1:進行
        self.num_players = 2
        self.sort_mode = "R" # "R": Reverse (デフォルト), "S": Slide
        self.players = []
        self.cur_idx = 0
        self.history = None
        self.msg = "READY"
        self.turn_count = 1

    def draw(self):
        print("Update Display...")
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        if self.state == 0:
            # --- 設定画面レイアウトの最適化 ---
            draw.text((10, 5), "MOLKKY SCORE", font=self.font_m, fill=0)
            # Playersの文字サイズをfont_mに変更し、Sort表示と横並びにスッキリ配置
            draw.text((10, 30), f"Players: {self.num_players}  Sort: {self.sort_mode}", font=self.font_m, fill=0)
            # ご指定いただいた操作ガイドテキスト
            draw.text((10, 60), "1 - 4: Set / 5: Reverse / 6: Slide", font=self.font_s, fill=0)
            draw.text((10, 85), "10: Start / R: Reset / U: Undo", font=self.font_s, fill=0)
        else:
            draw.rectangle((0, 0, self.width, 20), fill=0)
            draw.text((5, 2), f"T:{self.turn_count} {self.msg}", font=self.font_s, fill=1)

            for i, pl in enumerate(self.players):
                x = 10 if i < 2 else 130
                y = 25 + (i % 2) * 45
                draw.text((x, y), f"{pl['name']}:", font=self.font_s, fill=0)

                score_str = "OUT" if pl["out"] else str(pl["score"])
                if i == self.cur_idx:
                    draw.rectangle((x+30, y-2, x+75, y+22), fill=0)
                    draw.text((x+35, y), score_str, font=self.font_m, fill=1)
                else:
                    draw.text((x+35, y), score_str, font=self.font_m, fill=0)

                m_str = "X" * pl["miss"] if pl["miss"] > 0 else "-"
                draw.text((x, y+22), f"M:{m_str} S:{pl['sets']}", font=self.font_s, fill=0)

        self.epd.init()
        self.epd.display(self.epd.getbuffer(image))
        self.epd.sleep()

    def start_game(self):
        self.players = [{"name":f"P{i+1}","score":0,"miss":0,"sets":0,"out":False} for i in range(self.num_players)]
        self.state = 1
        self.cur_idx = 0
        self.turn_count = 1
        self.msg = "Go!"
        self.draw()

    def update_score(self, s):
        self.history = {"players":[dict(p) for p in self.players],"cur_idx":self.cur_idx,"msg":self.msg,"turn_count":self.turn_count}
        p = self.players[self.cur_idx]

        is_win = False
        is_out_event = False

        # --- 1. スコア/ミスの基本計算 ---
        if s == 0:
            p["miss"] += 1
            if p["miss"] >= 3:
                p["out"] = True
                self.msg = f"{p['name']} OUT"
                is_out_event = True
            else:
                self.msg = f"{p['name']} Miss"
                play_sound("miss")
        else:
            p["miss"] = 0
            p["score"] += s
            if p["score"] == 50:
                p["sets"] += 1
                self.msg = f"{p['name']} WIN"
                is_win = True
            elif p["score"] > 50:
                p["score"] = 25
                self.msg = "Burst!"
                play_sound("miss")  # バースト時も警告音(長め)
            else:
                self.msg = f"+{s}"
                play_sound("score")

        # --- 2. 生存プレイヤーの判定ロジック ---
        alive_players = [pl for pl in self.players if not pl["out"]]

        if len(alive_players) == 0:
            # 万が一全員失格になった場合、設定画面に戻す
            self.msg = "ALL OUT! RESET"
            play_sound("out")
            self.state = 0
            self.draw()
            return

        elif len(alive_players) == 1 and self.num_players > 1:
            # 複数人プレイで、残り1人になった場合、その人を50点にして勝利とする
            last_p = alive_players[0]
            last_p["score"] = 50
            last_p["sets"] += 1
            self.msg = f"{last_p['name']} WIN (Last)"
            is_win = True
            is_out_event = False  # 勝利音を優先

        # --- 3. 状態に応じたブザーと画面の確定処理 ---
        if is_win:
            play_sound("win")

            # ➔➔➔ セット終了時、設定されたモードに応じて投げ順（配列）を並び替え
            if self.sort_mode == "R":
                self.players.reverse()                      # Reverse: 配列を完全に反転
            elif self.sort_mode == "S":
                self.players = self.players[1:] + self.players[:1]  # Slide: 先頭を末尾に移動

            self.reset_scores()
            self.cur_idx = 0
            self.turn_count = 1
            self.draw()
            return
        elif is_out_event:
            play_sound("out")

        # --- 4. 次のプレイヤーへ手番を移す ---
        prev = self.cur_idx
        for _ in range(self.num_players):
            self.cur_idx = (self.cur_idx + 1) % self.num_players
            if not self.players[self.cur_idx]["out"]:
                break

        if self.cur_idx <= prev:
            self.turn_count += 1

        self.draw()

    def reset_scores(self):
        for p in self.players: p["score"]=0; p["miss"]=0; p["out"]=False

# ==========================================
# 3. メインループ
# ==========================================
if __name__ == "__main__":
    setup_hardware()
    game = MolkkyGame()
    game.draw()

    try:
        while True:
            key = scan_keypad()
            if key:
                print(f"Key Pressed: {key}")
                if game.state == 0:
                    if key in ["1", "2", "3", "4"]:
                        game.num_players = int(key)
                        game.draw()
                    elif key == "5":
                        game.sort_mode = "R"  # Reverseモードに設定
                        game.draw()
                    elif key == "6":
                        game.sort_mode = "S"  # Slideモードに設定
                        game.draw()
                    elif key == "10":
                        play_sound("start")  # 試合開始音
                        game.start_game()
                elif game.state == 1:
                    if key == "R":
                        game.state = 0
                        game.draw()
                    elif key == "U":
                        if game.history:
                            game.players = game.history["players"]
                            game.cur_idx = game.history["cur_idx"]
                            game.msg = "Undo"
                            game.turn_count = game.history["turn_count"]
                            game.history = None
                            game.draw()
                    elif key in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]:
                        game.update_score(int(key))
                    elif key == "O":
                        game.update_score(0)

            time.sleep(0.05)
    except KeyboardInterrupt:
        lgpio.gpiochip_close(h)
