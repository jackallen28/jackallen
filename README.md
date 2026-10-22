# Servo Trigger (Arduino Uno)

Standalone test sketches, separate from CircuitPath.

- `ServoTrigger/` - ultrasonic ranger (D7) or push button (D2) opens a continuous
  servo (D3) a quarter turn and lights the LED on D13; closes 5 s after release,
  stopping on a limit switch (D4) so the lid never drifts.
- `UltrasonicTest/` - diagnostic for an ultrasonic ranger that always reads -1.
- `ServoCalibrate/` - run first: interactive Serial Monitor tool to find the
  servo's stop value, direction and quarter-turn time, then prints the values
  to paste into `ServoTrigger.ino`.
