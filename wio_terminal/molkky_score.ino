#include <TFT_eSPI.h> // Wio Terminalの内蔵LCDライブラリ

TFT_eSPI tft = TFT_eSPI();

// ==========================================
// ゲーム状態の定義
// ==========================================
struct Player {
    String name;
    int score;
    int miss;
    int sets;
    bool out;
};

const int MAX_PLAYERS = 4;
Player players[MAX_PLAYERS];

int num_players = 2;   // 初期設定人数（2〜4人）
int cur_idx = 0;       // 現在手番のプレイヤー
int turn_count = 1;    // 現在のターン
String msg = "READY";  // メッセージライン
int state = 0;         // 0: 参加人数設定, 1: ゲーム進行

// 入力用の一時変数（方向キー右左で増減させる仮の入力点数）
int input_score = 0; 

// ==========================================
// 内蔵ブザーによる効果音 (音程と長さで表現)
// ==========================================
void play_sound(String pattern) {
    if (pattern == "start") {
        // 試合開始：ジャーン！
        analogWrite(WIO_BUZZER, 128); delay(150); analogWrite(WIO_BUZZER, 0); delay(20);
        analogWrite(WIO_BUZZER, 128); delay(300); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "score") {
        // スコア入力：短く高い音「ピッ」
        analogWrite(WIO_BUZZER, 128); delay(50); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "miss") {
        // 0点/バースト：少し低い音で「ピー」
        analogWrite(WIO_BUZZER, 64); delay(200); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "win") {
        // 勝利：「ピピピッ！」
        for(int i=0; i<3; i++) {
            analogWrite(WIO_BUZZER, 128); delay(60); analogWrite(WIO_BUZZER, 0); delay(60);
        }
    } else if (pattern == "out") {
        // 3ミスアウト：重々しく「ブブー」
        for(int i=0; i<2; i++) {
            analogWrite(WIO_BUZZER, 40); delay(250); analogWrite(WIO_BUZZER, 0); delay(100);
        }
    }
}

// ==========================================
// 画面描画処理
// ==========================================
void draw_screen() {
    tft.fillScreen(TFT_BLACK);

    if (state == 0) {
        // --- 設定画面 ---
        tft.setTextColor(TFT_YELLOW, TFT_BLACK);
        tft.setFreeFont(&FreeSansBold12pt7b);
        tft.drawString("MOLKKY SCORE", 50, 20);

        tft.setTextColor(TFT_WHITE, TFT_BLACK);
        tft.drawString("Players: " + String(num_players), 50, 70);

        tft.setFreeFont(&FreeSans9pt7b);
        tft.setTextColor(TFT_GREEN, TFT_BLACK);
        tft.drawString("Press Center to START", 50, 130);
        tft.drawString("Up/Down: Change Players", 50, 160);
    } else {
        // --- ゲーム進行画面 ---
        // 上部ステータスバー
        tft.fillRect(0, 0, 320, 30, TFT_NAVY);
        tft.setTextColor(TFT_WHITE, TFT_NAVY);
        tft.setFreeFont(&FreeSans9pt7b);
        tft.drawString("T: " + String(turn_count) + "   " + msg, 10, 5);

        // 各プレイヤーの情報表示
        for (int i = 0; i < num_players; i++) {
            int x = (i < 2) ? 10 : 165;
            int y = 40 + (i % 2) * 80;

            // 選択中のプレイヤーを枠線で囲む
            if (i == cur_idx) {
                tft.drawRect(x - 2, y - 2, 145, 74, TFT_YELLOW);
                tft.drawRect(x - 1, y - 1, 143, 72, TFT_YELLOW); // 太枠
            }

            // プレイヤー名
            tft.setFreeFont(&FreeSans9pt7b);
            tft.setTextColor(TFT_WHITE, TFT_BLACK);
            tft.drawString(players[i].name + ":", x + 5, y + 5);

            // スコア
            tft.setFreeFont(&FreeSansBold18pt7b);
            if (players[i].out) {
                tft.setTextColor(TFT_RED, TFT_BLACK);
                tft.drawString("OUT", x + 55, y + 2);
            } else {
                tft.setTextColor((i == cur_idx) ? TFT_YELLOW : TFT_CYAN, TFT_BLACK);
                tft.drawString(String(players[i].score), x + 55, y + 2);
            }

            // ミスとセット数
            tft.setFreeFont(&FreeSans9pt7b);
            tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
            String m_str = "";
            for (int m = 0; m < players[i].miss; m++) m_str += "X";
            if (m_str == "") m_str = "-";
            
            tft.drawString("M:" + m_str + " S:" + String(players[i].sets), x + 5, y + 45);
        }

        // 画面最下部に入力中の仮点数を表示
        tft.fillRect(0, 205, 320, 35, TFT_DARKGREY);
        tft.setTextColor(TFT_WHITE, TFT_DARKGREY);
        tft.setFreeFont(&FreeSans12pt7b);
        tft.drawString("Input Score: " + String(input_score), 10, 210);
        tft.setFreeFont(&FreeSans9pt7b);
        tft.drawString("[Press Center to Enter]", 170, 213);
    }
}

// ==========================================
// ゲーム初期化
// ==========================================
void start_game() {
    for (int i = 0; i < num_players; i++) {
        players[i] = {"P" + String(i + 1), 0, 0, 0, false};
    }
    state = 1;
    cur_idx = 0;
    turn_count = 1;
    input_score = 0;
    msg = "Go!";
    play_sound("start");
    draw_screen();
}

// ==========================================
// スコア確定ロジック
// ==========================================
void commit_score(int s) {
    Player &p = players[cur_idx];
    bool is_win = false;
    bool is_out_event = false;

    if (s == 0) {
        p.miss++;
        if (p.miss >= 3) {
            p.out = true;
            msg = p.name + " OUT";
            is_out_event = true;
        } else {
            msg = p.name + " Miss";
            play_sound("miss");
        }
    } else {
        p.miss = 0;
        p.score += s;
        if (p.score == 50) {
            p.sets++;
            msg = p.name + " WIN";
            is_win = true;
        } else if (p.score > 50) {
            p.score = 25;
            msg = "Burst!";
            play_sound("miss");
        } else {
            msg = "+" + String(s);
            play_sound("score");
        }
    }

    // 生存判定
    int alive_count = 0;
    int last_alive_idx = -1;
    for (int i = 0; i < num_players; i++) {
        if (!players[i].out) {
            alive_count++;
            last_alive_idx = i;
        }
    }

    if (alive_count == 0) {
        msg = "ALL OUT! RESET";
        play_sound("out");
        state = 0;
        draw_screen();
        return;
    } else if (alive_count == 1 && num_players > 1) {
        // 残り1人になったらその人を勝利とする
        players[last_alive_idx].score = 50;
        players[last_alive_idx].sets++;
        msg = players[last_alive_idx].name + " WIN (Last)";
        is_win = true;
        is_out_event = false;
    }

    if (is_win) {
        play_sound("win");
        // スコアのみリセット、セット数は維持
        for (int i = 0; i < num_players; i++) {
            players[i].score = 0;
            players[i].miss = 0;
            players[i].out = false;
        }
        cur_idx = 0;
        turn_count = 1;
        input_score = 0;
        draw_screen();
        return;
    } else if (is_out_event) {
        play_sound("out");
    }

    // 次のプレイヤーへ手番移動
    int prev = cur_idx;
    for (int i = 0; i < num_players; i++) {
        cur_idx = (cur_idx + 1) % num_players;
        if (!players[cur_idx].out) break;
    }
    if (cur_idx <= prev) turn_count++;

    input_score = 0; // 入力バッファリセット
    draw_screen();
}

// ==========================================
// セットアップ & メインループ
// ==========================================
void setup() {
    // 5方向スイッチの設定
    pinMode(WIO_5WAY_UP, INPUT_PULLUP);
    pinMode(WIO_5WAY_DOWN, INPUT_PULLUP);
    pinMode(WIO_5WAY_LEFT, INPUT_PULLUP);
    pinMode(WIO_5WAY_RIGHT, INPUT_PULLUP);
    pinMode(WIO_5WAY_PRESS, INPUT_PULLUP);

    // 上部3つのボタン設定 (左からA, B, C)
    pinMode(WIO_KEY_A, INPUT_PULLUP);
    pinMode(WIO_KEY_B, INPUT_PULLUP);
    pinMode(WIO_KEY_C, INPUT_PULLUP);

    // ブザーピンの設定
    pinMode(WIO_BUZZER, OUTPUT);

    // ディスプレイ初期化
    tft.begin();
    tft.setRotation(3); // 画面を横向きに設定
    draw_screen();
}

void loop() {
    // --- 状態0：設定画面のキー処理 ---
    if (state == 0) {
        if (digitalRead(WIO_5WAY_UP) == LOW) {
            num_players = (num_players == 4) ? 2 : num_players + 1;
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5WAY_DOWN) == LOW) {
            num_players = (num_players == 2) ? 4 : num_players - 1;
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5WAY_PRESS) == LOW) {
            start_game(); delay(300);
        }
    } 
    // --- 状態1：ゲーム進行画面のキー処理 ---
    else if (state == 1) {
        // 左右キーで入力点数を調整 (0〜12点)
        if (digitalRead(WIO_5WAY_LEFT) == LOW) {
            input_score = (input_score == 0) ? 12 : input_score - 1;
            draw_screen(); delay(150);
        }
        if (digitalRead(WIO_5WAY_RIGHT) == LOW) {
            input_score = (input_score == 12) ? 0 : input_score + 1;
            draw_screen(); delay(150);
        }

        // 上下キーで「プレイヤーの手動選択(スキップや手直し用)」
        if (digitalRead(WIO_5WAY_UP) == LOW) {
            do {
                cur_idx = (cur_idx == 0) ? num_players - 1 : cur_idx - 1;
            } while (players[cur_idx].out);
            draw_screen(); delay(250);
        }
        if (digitalRead(WIO_5WAY_DOWN) == LOW) {
            do {
                cur_idx = (cur_idx + 1) % num_players;
            } while (players[cur_idx].out);
            draw_screen(); delay(250);
        }

        // 5方向キー押し込みでスコア確定
        if (digitalRead(WIO_5WAY_PRESS) == LOW) {
            commit_score(input_score);
            delay(300);
        }

        // --- 上部ボタンの特殊割り当て ---
        // ボタンA (一番左): 0点(Miss)を即座に確定
        if (digitalRead(WIO_KEY_A) == LOW) {
            commit_score(0);
            delay(300);
        }
        // ボタンB (真ん中): 強制的に25点（バースト手直しなど）にする
        if (digitalRead(WIO_KEY_B) == LOW) {
            players[cur_idx].score = 25;
            players[cur_idx].miss = 0;
            msg = "Forced 25";
            play_sound("miss");
            draw_screen();
            delay(300);
        }
        // ボタンC (一番右): 設定画面（リセット）に戻る
        if (digitalRead(WIO_KEY_C) == LOW) {
            state = 0;
            draw_screen();
            delay(300);
        }
    }
    delay(20); // チャタリング・CPU負荷軽減
}
