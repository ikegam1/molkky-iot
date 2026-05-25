#include <TFT_eSPI.h> // Wio Terminalの内蔵LCDライブラリ
#include <Wire.h>     // I2C通信ライブラリ

TFT_eSPI tft = TFT_eSPI();

// --- VK36N16I (I2Cタッチキーパッド) の設定 ---
int vk36n16i_addr = 0x54; 
bool keypad_found = false;

// --- ゲーム状態の定義 ---
struct Player {
    String name;
    int score;
    int miss;
    int sets;
    bool out;
};

const int MAX_PLAYERS = 4;
Player players[MAX_PLAYERS];

struct GameState {
    Player p_backup[MAX_PLAYERS];
    int cur_p_idx;
    int turn;
    int set;
    String last_msg;
    bool exists;
};
GameState undo_state;

int num_players = 2;   
int turn_count = 1;    
String msg = "READY";  
int state = 0;         // 0: 設定画面, 1: ゲーム画面

int order_mode = 0;
int current_set = 1;
int set_order[MAX_PLAYERS]; 
int cur_order_idx = 0; 

// 本体キー操作用の仮入力スコア
int local_input_score = 1; 

int get_current_player_idx() {
    return set_order[cur_order_idx];
}

void save_undo_state() {
    for(int i=0; i<MAX_PLAYERS; i++) undo_state.p_backup[i] = players[i];
    undo_state.cur_p_idx = cur_order_idx;
    undo_state.turn = turn_count;
    undo_state.set = current_set;
    undo_state.last_msg = msg;
    undo_state.exists = true;
}

void play_sound(String pattern) {
    if (pattern == "start") {
        analogWrite(WIO_BUZZER, 128); delay(150); analogWrite(WIO_BUZZER, 0); delay(20);
        analogWrite(WIO_BUZZER, 128); delay(300); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "score") {
        analogWrite(WIO_BUZZER, 128); delay(50); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "miss") {
        analogWrite(WIO_BUZZER, 64); delay(200); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "win") {
        for(int i=0; i<3; i++) {
            analogWrite(WIO_BUZZER, 128); delay(60); analogWrite(WIO_BUZZER, 0); delay(60);
        }
    } else if (pattern == "out") {
        for(int i=0; i<2; i++) {
            analogWrite(WIO_BUZZER, 40); delay(250); analogWrite(WIO_BUZZER, 0); delay(100);
        }
    } else if (pattern == "key") {
        analogWrite(WIO_BUZZER, 128); delay(20); analogWrite(WIO_BUZZER, 0);
    } else if (pattern == "undo") {
        analogWrite(WIO_BUZZER, 128); delay(50); analogWrite(WIO_BUZZER, 0); delay(50);
        analogWrite(WIO_BUZZER, 64); delay(100); analogWrite(WIO_BUZZER, 0);
    }
}

// 起動時I2Cバススキャン
void scan_i2c_bus() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setFreeFont(&FreeSans9pt7b);
    tft.drawString("Scanning I2C Keypad...", 10, 50);
    
    for (int address = 1; address < 127; address++) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission(true) == 0) {
            vk36n16i_addr = address;
            keypad_found = true;
            tft.setTextColor(TFT_GREEN, TFT_BLACK);
            tft.drawString("Found Keypad at: 0x" + String(address, HEX), 10, 90);
            delay(1000);
            return;
        }
    }
    
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.drawString("Keypad NOT found!", 10, 90);
    tft.drawString("Running in Standalone Mode", 10, 120);
    delay(1500);
}

// キーパッド読み取り
int read_vk36n16i_key() {
    if (!keypad_found) return -2;

    uint16_t key_bits = 0;
    Wire.beginTransmission(vk36n16i_addr);
    Wire.write(0x08);
    if (Wire.endTransmission(true) != 0) return -2; 

    Wire.requestFrom(vk36n16i_addr, 2);
    if (Wire.available() == 2) {
        key_bits = Wire.read();
        key_bits |= (Wire.read() << 8);
    } else {
        return -2;
    }

    if (key_bits != 0 && key_bits != 0xFFFF) {
        for (int i = 0; i < 16; i++) {
            if ((key_bits >> i) & 0x01) return i;
        }
    }
    
    uint16_t inv_bits = ~key_bits;
    if (inv_bits != 0 && inv_bits != 0xFFFF) {
        for (int i = 0; i < 16; i++) {
            if ((inv_bits >> i) & 0x01) return i;
        }
    }
    return -2; 
}

// キーパッドマトリクス対応表（D=UNDO）
String map_key_to_value(int raw_code) {
    switch(raw_code) {
        // --- 1段目 ---
        case 12: return "1";    // 物理[1]
        case 3:  return "2";    // 物理[2]
        case 7:  return "3";    // 物理[3]
        case 8:  return "10";   // 物理[A] -> 10点
        
        // --- 2段目 ---
        case 13: return "4";    // 物理[4]
        case 2:  return "5";    // 物理[5]
        case 6:  return "6";    // 物理[6]
        case 9:  return "11";   // 物理[B] -> 11点
        
        // --- 3段目 ---
        case 14: return "7";    // 物理[7]
        case 1:  return "8";    // 物理[8]
        case 5:  return "9";    // 物理[9]
        case 10: return "12";   // 物理[C] -> 12点
        
        // --- 4段目 ---
        case 11: return "UNDO"; // 物理[D] -> Undo実行
        case 0:  return "0";    // 物理[0] -> 0点(Miss)
        case 4:  return "0";    // 物理[#] -> 0点(Miss)
        case 15: return "0";    // 物理[*] -> 0点(Miss)
        
        default: return "";
    }
}

void calculate_set_order() {
    if (order_mode == 0) {
        if (current_set % 2 != 0) {
            for (int i = 0; i < num_players; i++) set_order[i] = i;
        } else {
            for (int i = 0; i < num_players; i++) set_order[i] = (num_players - 1) - i;
        }
    } else {
        int start_offset = (current_set - 1) % num_players;
        for (int i = 0; i < num_players; i++) {
            set_order[i] = (start_offset + i) % num_players;
        }
    }
    cur_order_idx = 0;
}

void draw_screen() {
    tft.fillScreen(TFT_BLACK);

    if (state == 0) {
        tft.setTextColor(TFT_YELLOW, TFT_BLACK);
        tft.setFreeFont(&FreeSansBold12pt7b);
        tft.drawString("MOLKKY SCORE", 50, 20);

        tft.setTextColor(TFT_WHITE, TFT_BLACK);
        tft.setFreeFont(&FreeSans9pt7b);
        tft.drawString("Players: " + String(num_players), 50, 60);
        
        String mode_str = (order_mode == 0) ? "Reverse" : "Slide";
        tft.drawString("Order: " + mode_str, 50, 90);

        tft.setTextColor(TFT_GREEN, TFT_BLACK);
        tft.drawString("Press Center to START", 50, 130);
        tft.drawString("Up/Down: Change Players", 50, 160);
        
        tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
        tft.drawString("Left: Slide  /  Right: Reverse", 50, 195);
        
        tft.setTextFont(1);
        if(keypad_found) {
            tft.setTextColor(TFT_GREEN, TFT_BLACK);
            tft.drawString("Keypad: Connected (0x" + String(vk36n16i_addr, HEX) + ")", 10, 230);
        } else {
            tft.setTextColor(TFT_ORANGE, TFT_BLACK);
            tft.drawString("Keypad: Standalone Mode (No Keypad)", 10, 230);
        }
    } else {
        tft.fillRect(0, 0, 320, 30, TFT_NAVY);
        tft.setTextColor(TFT_WHITE, TFT_NAVY);
        tft.setFreeFont(&FreeSans9pt7b);
        
        String mode_char = (order_mode == 0) ? "(R)" : "(S)";
        tft.drawString("S:" + String(current_set) + mode_char + " T:" + String(turn_count) + " " + msg, 10, 5);

        int current_active_player = get_current_player_idx();

        for (int i = 0; i < num_players; i++) {
            int x = (i < 2) ? 10 : 165;
            int y = 40 + (i % 2) * 80;

            if (i == current_active_player) {
                tft.drawRect(x - 2, y - 2, 145, 74, TFT_YELLOW);
                tft.drawRect(x - 1, y - 1, 143, 72, TFT_YELLOW); 
            }

            tft.setFreeFont(&FreeSans9pt7b);
            tft.setTextColor(TFT_WHITE, TFT_BLACK);
            tft.drawString(players[i].name + ":", x + 5, y + 5);

            tft.setFreeFont(&FreeSansBold18pt7b);
            if (players[i].out) {
                tft.setTextColor(TFT_RED, TFT_BLACK);
                tft.drawString("OUT", x + 55, y + 2);
            } else {
                tft.setTextColor((i == current_active_player) ? TFT_YELLOW : TFT_CYAN, TFT_BLACK);
                tft.drawString(String(players[i].score), x + 55, y + 2);
            }

            tft.setFreeFont(&FreeSans9pt7b);
            tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
            String m_str = "";
            for (int m = 0; m < players[i].miss; m++) m_str += "X";
            if (m_str == "") m_str = "-";
            
            tft.drawString("M:" + m_str + " S:" + String(players[i].sets), x + 5, y + 45);
        }

        // 方向キー入力値(Input)の可視化表示
        tft.fillRect(0, 205, 320, 35, TFT_DARKGREY);
        tft.setTextColor(TFT_YELLOW, TFT_DARKGREY);
        tft.setFreeFont(&FreeSans9pt7b);
        tft.drawString("Input: " + String(local_input_score) + "   D:Undo  [0-C]:Score", 15, 213);   
    }
}

void start_game() {
    for (int i = 0; i < num_players; i++) {
        players[i] = {"P" + String(i + 1), 0, 0, 0, false};
    }
    state = 1;
    current_set = 1;   
    calculate_set_order(); 
    turn_count = 1;
    local_input_score = 1; 
    msg = "Go!";
    undo_state.exists = false; 
    play_sound("start");
    draw_screen();
}

void commit_score(int s) {
    save_undo_state(); 

    int p_idx = get_current_player_idx();
    Player &p = players[p_idx];
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

    int alive_count = 0;
    int last_alive_p_idx = -1;
    for (int i = 0; i < num_players; i++) {
        if (!players[i].out) {
            alive_count++;
            last_alive_p_idx = i;
        }
    }

    if (alive_count == 0) {
        msg = "ALL OUT! RESET";
        play_sound("out");
        state = 0;
        draw_screen();
        return;
    } else if (alive_count == 1 && num_players > 1) {
        players[last_alive_p_idx].score = 50;
        players[last_alive_p_idx].sets++;
        msg = players[last_alive_p_idx].name + " WIN (Last)";
        is_win = true;
        is_out_event = false;
    }

    if (is_win) {
        play_sound("win");
        current_set++;
        calculate_set_order(); 

        for (int i = 0; i < num_players; i++) {
            players[i].score = 0;
            players[i].miss = 0;
            players[i].out = false;
        }
        
        turn_count = 1;
        local_input_score = 1;
        draw_screen();
        return;
    } else if (is_out_event) {
        play_sound("out");
    }

    int prev_order_idx = cur_order_idx;
    for (int i = 0; i < num_players; i++) {
        cur_order_idx = (cur_order_idx + 1) % num_players;
        if (!players[get_current_player_idx()].out) break;
    }
    if (cur_order_idx <= prev_order_idx) turn_count++;

    local_input_score = 1; 
    draw_screen();
}

void perform_undo() {
    if (!undo_state.exists || state == 0) return; 

    play_sound("undo");
    
    for(int i=0; i<MAX_PLAYERS; i++) players[i] = undo_state.p_backup[i];
    cur_order_idx = undo_state.cur_p_idx;
    turn_count = undo_state.turn;
    
    if (current_set != undo_state.set) {
        current_set = undo_state.set;
        calculate_set_order();
        cur_order_idx = undo_state.cur_p_idx; 
    }
    
    msg = undo_state.last_msg + " (Undo)";
    undo_state.exists = false; 
    local_input_score = 1; 
    
    draw_screen();
}

void setup() {
    Wire.begin(); 
    Wire.setClock(100000); 
    
    pinMode(WIO_5S_UP, INPUT_PULLUP);
    pinMode(WIO_5S_DOWN, INPUT_PULLUP);
    pinMode(WIO_5S_LEFT, INPUT_PULLUP);
    pinMode(WIO_5S_RIGHT, INPUT_PULLUP);
    pinMode(WIO_5S_PRESS, INPUT_PULLUP);

    // Wio Terminal 上部ABCキーの初期化
    pinMode(WIO_KEY_A, INPUT_PULLUP);
    pinMode(WIO_KEY_B, INPUT_PULLUP);
    pinMode(WIO_KEY_C, INPUT_PULLUP);

    pinMode(WIO_BUZZER, OUTPUT);

    tft.begin();
    tft.setRotation(3); 
    
    scan_i2c_bus(); 
    draw_screen();
}

int last_key_code = -2; 
bool key_released = true;

void loop() {
    // --- 1. キーパッド (VK36N16I) の処理 ---
    if (keypad_found) {
        int current_key_code = read_vk36n16i_key();
        if (current_key_code >= 0) { 
            if (key_released || current_key_code != last_key_code) {
                play_sound("key");
                String key_val = map_key_to_value(current_key_code);
                
                if (state == 1) { 
                    if (key_val == "UNDO") {
                        perform_undo();
                    } else if (key_val != "") {
                        commit_score(key_val.toInt());
                    }
                }
                key_released = false;
            }
            last_key_code = current_key_code;
        } else {
            key_released = true;
        }
    }

    // --- 2. Wio Terminal 本体スイッチ(ジョイスティック)の処理 ---
    if (state == 0) {
        if (digitalRead(WIO_5S_UP) == LOW) {
            num_players = (num_players == 4) ? 2 : num_players + 1;
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5S_DOWN) == LOW) {
            num_players = (num_players == 2) ? 4 : num_players - 1;
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5S_LEFT) == LOW) {
            order_mode = 1; 
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5S_RIGHT) == LOW) {
            order_mode = 0; 
            draw_screen(); delay(200);
        }
        if (digitalRead(WIO_5S_PRESS) == LOW) {
            start_game(); delay(300);
        }
    } 
    else if (state == 1) {
        if (digitalRead(WIO_5S_UP) == LOW) {
            local_input_score++;
            if (local_input_score > 12) local_input_score = 0;
            play_sound("key");
            draw_screen(); 
            delay(200);
        }
        if (digitalRead(WIO_5S_DOWN) == LOW) {
            local_input_score--;
            if (local_input_score < 0) local_input_score = 12;
            play_sound("key");
            draw_screen();
            delay(200);
        }
        if (digitalRead(WIO_5S_PRESS) == LOW) {
            commit_score(local_input_score);
            delay(300);
        }
    }

    // --- 3. Wio Terminal 上部ボタン (A, B, C) の固有処理 ---
    if (state == 1) {
        // KEY_A: Undo処理
        if (digitalRead(WIO_KEY_A) == LOW) {
            perform_undo();
            delay(300);
        }
        // 【修正】KEY_B: 強制Burst処理（37点ルール等で使用。スコアを25点に戻してターン交代）
        else if (digitalRead(WIO_KEY_B) == LOW) {
            save_undo_state(); // 戻せるようにバックアップを取る
            play_sound("miss");
            
            int p_idx = get_current_player_idx();
            players[p_idx].score = 25; // 強制的に25点（バースト状態）へ戻す
            players[p_idx].miss = 0;   // ミスカウントはリセット
            msg = "Forced Burst!";
            
            // 次のプレイヤーへターンを回す
            int prev_order_idx = cur_order_idx;
            for (int i = 0; i < num_players; i++) {
                cur_order_idx = (cur_order_idx + 1) % num_players;
                if (!players[get_current_player_idx()].out) break;
            }
            if (cur_order_idx <= prev_order_idx) turn_count++;

            local_input_score = 1; 
            draw_screen();
            delay(300);
        }
        // KEY_C: Reset処理 (設定画面へ戻る)
        else if (digitalRead(WIO_KEY_C) == LOW) {
            play_sound("undo");
            state = 0; 
            draw_screen();
            delay(300);
        }
    }
    
    delay(20); 
}
