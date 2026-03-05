/*
 * ============================================================
 *  4DOF ROBOT ARM - Single ESP32 Pick & Place
 *  Servos: Base | Shoulder | Elbow
 *  Commands via Serial (USB from Python):
 *    'A' → Amazon   → Place at 30°
 *    'M' → Meesho   → Place at 60°
 *    'F' → Flipkart → Place at 90°
 * ============================================================
 */

#include <ESP32Servo.h>

// ── Pin Definitions ────────────────────────────────────────
#define PIN_BASE      18   // Base servo signal pin
#define PIN_SHOULDER  19   // Shoulder servo signal pin
#define PIN_ELBOW     21   // Elbow servo signal pin

// ── Home Position Angles ───────────────────────────────────
#define HOME_BASE       0   // Base at 0° (pick zone)
#define HOME_SHOULDER  90   // Shoulder upright
#define HOME_ELBOW     90   // Elbow neutral

// ── Pick Position Angles ───────────────────────────────────
#define PICK_SHOULDER  130  // Shoulder lowers arm down
#define PICK_ELBOW     60   // Elbow extends forward

// ── Place Position Angles (shoulder/elbow) ─────────────────
#define PLACE_SHOULDER 130  // Same lower position to drop
#define PLACE_ELBOW    60

// ── Base Target Angles per Brand ──────────────────────────
#define BASE_AMAZON    30
#define BASE_MEESHO    60
#define BASE_FLIPKART  90

// ── Timing ────────────────────────────────────────────────
#define MOVE_DELAY      15   // ms between each 1° step (servo speed)
#define HOLD_DELAY     800   // ms to hold at pick/place position

Servo baseServo;
Servo shoulderServo;
Servo elbowServo;

// Current angles
int curBase     = HOME_BASE;
int curShoulder = HOME_SHOULDER;
int curElbow    = HOME_ELBOW;

// ── Smooth Move Helper ─────────────────────────────────────
void moveServo(Servo &servo, int &current, int target) {
  if (current == target) return;
  int step = (target > current) ? 1 : -1;
  while (current != target) {
    current += step;
    servo.write(current);
    delay(MOVE_DELAY);
  }
}

// ── Go to Home Position ────────────────────────────────────
void goHome() {
  Serial.println("[ARM] Going to HOME position...");
  moveServo(elbowServo,    curElbow,    HOME_ELBOW);
  moveServo(shoulderServo, curShoulder, HOME_SHOULDER);
  moveServo(baseServo,     curBase,     HOME_BASE);
  Serial.println("[ARM] HOME reached.");
}

// ── Full Pick & Place Sequence ─────────────────────────────
void pickAndPlace(int targetBaseAngle, const char* label) {
  Serial.print("[ARM] Starting pick & place for: ");
  Serial.println(label);

  // STEP 1: Lower arm to PICK position
  Serial.println("[ARM] Step 1 - Lowering to pick...");
  moveServo(shoulderServo, curShoulder, PICK_SHOULDER);
  moveServo(elbowServo,    curElbow,    PICK_ELBOW);
  delay(HOLD_DELAY);  // Simulate grip (end effector off for now)

  // STEP 2: Lift arm back up
  Serial.println("[ARM] Step 2 - Lifting up...");
  moveServo(elbowServo,    curElbow,    HOME_ELBOW);
  moveServo(shoulderServo, curShoulder, HOME_SHOULDER);

  // STEP 3: Rotate base to target zone
  Serial.print("[ARM] Step 3 - Rotating base to ");
  Serial.print(targetBaseAngle);
  Serial.println("°...");
  moveServo(baseServo, curBase, targetBaseAngle);

  // STEP 4: Lower arm to PLACE position
  Serial.println("[ARM] Step 4 - Lowering to place...");
  moveServo(shoulderServo, curShoulder, PLACE_SHOULDER);
  moveServo(elbowServo,    curElbow,    PLACE_ELBOW);
  delay(HOLD_DELAY);  // Simulate release

  // STEP 5: Return to home
  Serial.println("[ARM] Step 5 - Returning home...");
  moveServo(elbowServo,    curElbow,    HOME_ELBOW);
  moveServo(shoulderServo, curShoulder, HOME_SHOULDER);
  moveServo(baseServo,     curBase,     HOME_BASE);

  Serial.print("[ARM] ✓ Done! Object placed at ");
  Serial.print(targetBaseAngle);
  Serial.println("°. Ready for next QR.");
  Serial.println("READY");  // Python listens for this
}

// ── Setup ──────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);

  // Attach servos
  baseServo.attach(PIN_BASE,     500, 2400);
  shoulderServo.attach(PIN_SHOULDER, 500, 2400);
  elbowServo.attach(PIN_ELBOW,   500, 2400);

  // Move to home on startup
  baseServo.write(HOME_BASE);
  shoulderServo.write(HOME_SHOULDER);
  elbowServo.write(HOME_ELBOW);
  delay(1000);

  Serial.println("=============================");
  Serial.println(" Robot Arm Ready!");
  Serial.println(" Waiting for QR command...");
  Serial.println(" A=Amazon | M=Meesho | F=Flipkart");
  Serial.println("=============================");
  Serial.println("READY");
}

// ── Loop ───────────────────────────────────────────────────
void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    // Flush any extra bytes
    while (Serial.available()) Serial.read();

    if (cmd == 'A' || cmd == 'a') {
      pickAndPlace(BASE_AMAZON, "AMAZON (30 deg)");
    }
    else if (cmd == 'M' || cmd == 'm') {
      pickAndPlace(BASE_MEESHO, "MEESHO (60 deg)");
    }
    else if (cmd == 'F' || cmd == 'f') {
      pickAndPlace(BASE_FLIPKART, "FLIPKART (90 deg)");
    }
    else if (cmd == 'H' || cmd == 'h') {
      goHome();
      Serial.println("READY");
    }
    else {
      Serial.print("[WARN] Unknown command: ");
      Serial.println(cmd);
      Serial.println("READY");
    }
  }
}
