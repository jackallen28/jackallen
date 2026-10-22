/*
  ServoCalibrate - find the right values for ServoTrigger's continuous servo

  Upload this, open the Serial Monitor at 9600 baud, and set the line ending
  to "Newline". Type a command and press Enter.

  Do it with the lid attached and the same power supply you'll use for real:
  the servo's speed changes with load and voltage.

  Put a mark (tape or pen) on the servo horn so you can see where it stops.

  STEP 1 - stop value (servo should sit perfectly still)
    +   /  -     nudge the stop value up / down by 1 (servo holds at stop)
    Keep nudging until the horn doesn't creep at all. Usually 88-92.

  STEP 2 - direction
    o            do one "open" move
    c            do one "close" move
    r            reverse: swap the open and close directions
    Close the lid by hand first, then press o. If the lid goes the wrong
    way, press r.

  STEP 3 - quarter-turn time
    t400         set the move time to 400 ms (any number)
    f            full-turn test: 4 open moves in a row - the mark should end
                 up exactly where it started. Too far = shorter time, not far
                 enough = longer time. Then check o / c on the lid itself.
    v30          set the speed: how far from stop (1-90, default 30).
                 Slower = more accurate but weaker.

  STEP 4 - copy the values
    ?            print the values to paste into ServoTrigger.ino
*/

#include <Servo.h>

const int SERVO_PIN = 3;

Servo servo;
int stopValue = 90;
int speedOffset = 30;          // how far from stopValue to drive when moving
int openDirection = -1;        // -1 = open is below stop, +1 = open is above
unsigned long turnTimeMs = 350;

int openValue()  { return constrain(stopValue + openDirection * speedOffset, 0, 180); }
int closeValue() { return constrain(stopValue - openDirection * speedOffset, 0, 180); }

// Same move as ServoTrigger's turnServo(), then hold at stop so creep shows up.
void move(int speed) {
  servo.write(speed);
  delay(turnTimeMs);
  servo.write(stopValue);
}

void printValues() {
  Serial.println();
  Serial.println("// ---- paste into ServoTrigger.ino ----");
  Serial.print("const int           SERVO_STOP   = "); Serial.print(stopValue);   Serial.println(";");
  Serial.print("const int           SERVO_OPEN   = "); Serial.print(openValue()); Serial.println(";");
  Serial.print("const int           SERVO_CLOSE  = "); Serial.print(closeValue()); Serial.println(";");
  Serial.print("const unsigned long TURN_TIME_MS = "); Serial.print(turnTimeMs);  Serial.println(";");
  Serial.println();
}

void printHelp() {
  Serial.println("Commands: + -  (stop)   o c r  (direction)   t<ms> v<speed> f  (turn)   ?  (values)");
}

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50);
  servo.attach(SERVO_PIN);
  servo.write(stopValue);
  Serial.println("Servo calibration");
  printHelp();
  printValues();
}

void loop() {
  if (!Serial.available()) {
    return;
  }

  char cmd = Serial.read();
  switch (cmd) {
    case '+':
    case '-':
      stopValue = constrain(stopValue + (cmd == '+' ? 1 : -1), 0, 180);
      servo.write(stopValue);
      Serial.print("Stop value: ");
      Serial.println(stopValue);
      break;

    case 'o':
      Serial.println("Open move");
      move(openValue());
      break;

    case 'c':
      Serial.println("Close move");
      move(closeValue());
      break;

    case 'r':
      openDirection = -openDirection;
      Serial.print("Reversed. Open = ");
      Serial.print(openValue());
      Serial.print(", close = ");
      Serial.println(closeValue());
      break;

    case 'f':
      Serial.println("Full turn: 4 open moves");
      for (int i = 0; i < 4; i++) {
        move(openValue());
        delay(500);
      }
      break;

    case 't': {
      long ms = Serial.parseInt();
      if (ms > 0) {
        turnTimeMs = ms;
      }
      Serial.print("Turn time: ");
      Serial.print(turnTimeMs);
      Serial.println(" ms");
      break;
    }

    case 'v': {
      long v = Serial.parseInt();
      if (v >= 1 && v <= 90) {
        speedOffset = v;
      }
      Serial.print("Speed: ");
      Serial.print(speedOffset);
      Serial.print("  (open = ");
      Serial.print(openValue());
      Serial.print(", close = ");
      Serial.print(closeValue());
      Serial.println(")");
      break;
    }

    case '?':
      printValues();
      break;

    case '\n':
    case '\r':
    case ' ':
      break;  // ignore line endings

    default:
      printHelp();
      break;
  }
}
