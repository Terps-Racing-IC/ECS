#include <Arduino.h>
#include <SPI.h>
#include <ACAN2515.h>
#include <cstdint>

#define HONE_PIN 10 // CHANGE TO WHATEVER WE WIRE ONE OF THE BUTTONS TO

const bool DEBUG = true;

const uint32_t MOTOR_CAN_ID = 0x02; 
ACAN2515 can(PIN_CAN_CS, SPI, 22); 

float HOME = 0.0;     // Motor travel center
bool is_honed = false;// Whether motor should be considered honed. Only needed if using the non-V3.0 AK45-36
uint32_t motor_last_seen = 0;
int16_t steerAng = 0; // Front steering wheel angle in tenths of a degree.
int16_t fixed_gain= 0;// Fixed gain coef for fixed gain mode. Multiplied by 0.1 to get final gain
uint16_t rpm = 0;     // Engine RPM
float speed = 0;      // Vehicle speed in MPH
float kp = 0.0;       // Global kp value. Needs to be ramped to target after honing. SHOULD BE INITIALiZED TO WHATEVER HONE_KP IS
float target_kp =50.0;// Target global kp value after honing
float kd = 1.0;       // Global kd value
RWSMode mode = RWSMode::SPD_GAIN;// Global mode value

// MIT Mode bounds
#define P_MIN -12.5f
#define P_MAX 12.5f
#define KP_MIN 0.0f
#define KP_MAX 500.0f
#define KD_MIN 0.0f
#define KD_MAX 5.0f
// AK45-36 Bounds
#define V_MIN -10.0f //approximate for 50RPM
#define V_MAX 10.0f
#define T_MIN -24.0f 
#define T_MAX 24.0f

struct TelemetryPacket {
  float position;
  float velocity;
  float torque;
  int temp_c;
  int error_flag;
};

// Special MIT commands:
std::uint8_t MIT_ENTER[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFC};
std::uint8_t MIT_EXIT[]  = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD};
std::uint8_t MIT_ZERO[]  = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFE};

int float_to_uint(float x, float x_min, float x_max, int bits) {
  float span = x_max - x_min;
  if (x < x_min) x = x_min;
  if (x > x_max) x = x_max;
  return (int) ((x - x_min) * ((float)((1 << bits) - 1)) / span);
}

float uint_to_float(int x_int, float x_min, float x_max, int bits) {
  float span = x_max - x_min;
  float offset = x_min;
  return ((float)x_int * span / ((float)((1 << bits) - 1))) + offset;
}

void pack_send_ControlFrame(float p_in, float v_in, float kp_in, float kd_in, float t_in) {
  int p_int = float_to_uint(p_in, P_MIN, P_MAX, 16);
  int v_int = float_to_uint(v_in, V_MIN, V_MAX, 12);
  int kp_int = float_to_uint(kp_in, KP_MIN, KP_MAX, 12);
  int kd_int = float_to_uint(kd_in, KD_MIN, KD_MAX, 12);
  int t_int = float_to_uint(t_in, T_MIN, T_MAX, 12);

  CANMessage msg;
  msg.id = MOTOR_CAN_ID;
  msg.ext = false; 
  msg.len = 8;
  msg.data[0] = p_int >> 8;
  msg.data[1] = p_int & 0xFF;
  msg.data[2] = v_int >> 4;
  msg.data[3] = ((v_int & 0xF) << 4) | (kp_int >> 8);
  msg.data[4] = kp_int & 0xFF;
  msg.data[5] = kd_int >> 4;
  msg.data[6] = ((kd_int & 0xF) << 4) | (t_int >> 8);
  msg.data[7] = t_int & 0xFF;
  
  can.tryToSend(msg);
}

TelemetryPacket unpack_TelemetryFrame(const uint8_t* data) {
  // data[0] is the motor ID
  TelemetryPacket result;
  
  // Reconstruct 12 and 16 bit integers
  int p_int = (data[1] << 8) | data[2];
  int v_int = (data[3] << 4) | (data[4] >> 4);
  int t_int = ((data[4] & 0x0F) << 8) | data[5];
  int temp_raw = data[6];
  result.error_flag = data[7];

  // Decompress back to floats using your defined boundaries
  result.position = uint_to_float(p_int, P_MIN, P_MAX, 16);
  result.velocity = uint_to_float(v_int, V_MIN, V_MAX, 12);
  result.torque = uint_to_float(t_int, T_MIN, T_MAX, 12);
  result.temp_c = temp_raw - 40;

  // Print formatted output
  if (DEBUG) {
    Serial.print("Motor ID: ");
    Serial.print(data[0]);
    Serial.print(" | Pos(rad): "); 
    if (result.position >= 0.0) {Serial.print(" ");}
    Serial.print(result.position, 3);
    Serial.print(" | Vel(rad/s): "); 
    if (result.velocity >= 0.0) {Serial.print(" ");}
    Serial.print(result.velocity, 3);
    Serial.print(" | Torq(Nm): "); 
    if (result.torque >= 0.0) {Serial.print(" ");}
    if (abs(result.torque) < 10.0) {Serial.print(" ");}
    Serial.print(result.torque, 2);
    Serial.print(" | Temp(C): ");
    Serial.print(result.temp_c);
    Serial.print(" | Err: 0x"); 
    Serial.println(result.error_flag, HEX);
  }

  return result;
}

void test_SINEWAVE () {
  // Generate a smooth sine wave based on uptime
  // millis() / 1000.0 converts to seconds.
  // This creates a wave that completes one full cycle every ~6.28 seconds.
  float time_sec = millis() / 1000.0;
  
  // Multiply by 0.5 to limit the sweep from -0.5 to +0.5 radians
  float target_pos = HOME + (sin(time_sec)*0.4); 

  // Ultra-safe, low-current gains for 3.2A bench supply
  float kp = 10.0;  // Very soft stiffness, should roughly = 2Nm max torque
  float kd = 0.2;  // Light damping to prevent jitter
  float target_vel = 0.0; // Velocity feed-forward (keep 0 for now)
  float feed_forward_torque = 0.0; 

  // 3. Send the command frame
  pack_send_ControlFrame(target_pos, target_vel, kp, kd, feed_forward_torque);
}

// HONING ROUTINE ENUMS
/* Honing phase enumerator.
  START = motor is rotating in first direction to find the first bound
  DIR_CHANGE = motor is rotating in second direction to find the second bound
  GO_HOME = motor is rotating in first direction towards its home
  END = motor honing is complete, target position is set at home
*/
enum class HonePhase : unsigned char {
  START = 0,
  DIR_CHANGE = 1,
  GO_HOME = 2,
  END = 3
};

/* Sets the global 'home' variable by rotating the motor from lock to lock.
  Returns TRUE if the honing process was succesful.
  Returns FALSE if the motor throws an error code during honing.
*/
bool hone_find_center() {
  float target_pos = 0.0;
  float hone_kp = 10.0;
  float hone_kd = 0.2;
  float target_rads = 1.04; // Approx radians per second target for motor travel
  // FF Torque = 0.0
  uint32_t hone_time = millis();
  float bound_torque = 2;//1.0;

  float bound1;
  float bound2; 
  // Bound2 is found by subtracting from target pos so it will be less


  HonePhase phase = HonePhase::START; // This controls what phase we're in for honing
  bool error = false;
  CANMessage rxMsg;
  TelemetryPacket motorState = {0};
  Serial.println("Starting honing...");
  while (error == false) {
    uint32_t current_time = millis();

    while (can.receive(rxMsg)) {
      if (rxMsg.id == MOTOR_CAN_ID) {
        // Process all motor data to get to the most recent frame, ignore non-motor IDs
        motorState = unpack_TelemetryFrame(rxMsg.data);
      }
    }

    if (motorState.error_flag != 0) {
      Serial.println("Encountered motor error flag when honing");
      error = true; // Uh oh
    }

    if (current_time - hone_time >= 10) {
      float time_delta = (float(current_time) - float(hone_time))/1000; 
      hone_time = current_time;
      pack_send_ControlFrame(target_pos, 0.0, hone_kp, hone_kd, 0.0);
      switch(phase) {
        case HonePhase::START:
          if (abs(motorState.torque) > bound_torque) {
            bound1 = motorState.position;
            target_pos = motorState.position;
            phase = HonePhase::DIR_CHANGE;
            Serial.println("Found bound 1...");
          } else {
            target_pos += target_rads*time_delta;
          }
          break;
        case HonePhase::DIR_CHANGE:
          if (abs(motorState.torque) > bound_torque && abs(bound1 - motorState.position) > 0.1 ) {
            bound2 = motorState.position;
            target_pos = motorState.position;
            HOME = (bound1 + bound2)/2; // Average the bounds
            Serial.println("Found bound 2...");
            phase = HonePhase::GO_HOME;
          } else {
            target_pos -= target_rads*time_delta;
          }
          break;
        case HonePhase::GO_HOME:
          target_pos += target_rads*time_delta;
          if (target_pos > HOME) {
            target_pos = HOME; // Setting this means that next loop the motor will be commanded to its home
            Serial.println("Found home...");
            phase = HonePhase::END; // Then we will return after that command
          }
          break;
        default:
          return true;
      }
    }
  }
  return false; 
  // Wrap in the error flag case with a fall-through return in case cosmic bit flip fiasco
}

/* This function slowly ramps up kp after honing to avoid the motor snapping abruptly */
void ramp_kp() {
  // Control code runs at 100Hz
  float ramp_s = 5.0; // How many seconds the ramping process should take

  if (kp < target_kp) {
    kp += target_kp/(ramp_s*100); // this will add a fraction of the KP value every tick to slowly increase it linearly
  }
  if (kp >= target_kp) {
    kp = target_kp;
  }
}


// MODE OPTIONS
enum class RWSMode : uint8_t {
  SPD_GAIN = 0,       // Dynamic speed gain function
  FIXED_GAIN = 1,     // Gain as commanded by dashboard
  OFF = 2,            // Motor limp
};

// SPEED GAIN
const int NUM_SPEEDS = 5;
const int NUM_ANGLES = 4;

// X-Axis: Vehicle Speed (MPH)
float speed_bps[NUM_SPEEDS] = {0.0, 15.0, 30.0, 45.0, 60.0};

// Y-Axis: Absolute Front Steering Angle (Normalized 0.0 to 1.0)
// Use absolute angle because cornering behavior is generally symmetrical left/right.
float angle_bps[NUM_ANGLES] = {0.0, 0.33, 0.66, 1.0};

// Z-Axis: Rear Steering Gain Multipliers
// Matrix format: gain_table[Speed Index][Angle Index]
// Negative = Counter-phase (agile), Positive = In-phase (stable), 0.0 = Locked (skidpad)
float gain_table[NUM_SPEEDS][NUM_ANGLES] = {
  { 0.0,   0.0,   0.0,   0.0  },  // 0 MPH: Parked, zero gain
  {-0.2,  -0.4,  -0.6,  -0.8  },  // 15 MPH: Tight hairpins, aggressive counter-phase
  { 0.0,   0.0,   0.0,  -0.2  },  // 30 MPH: Skidpad speeds (0.0), slight counter on heavy lock
  { 0.1,   0.2,   0.1,   0.0  },  // 45 MPH: Slalom sweepers, slight in-phase for stability
  { 0.3,   0.4,   0.3,   0.1  }   // 60 MPH: High-speed straights, strong in-phase tracking
};

float get_2d_gain(float current_speed, float current_angle) {
  // Clamp inputs to the table boundaries
  current_speed = constrain(current_speed, speed_bps[0], speed_bps[NUM_SPEEDS-1]);
  current_angle = constrain(fabs(current_angle), angle_bps[0], angle_bps[NUM_ANGLES-1]);

  // Find the bounding indices for Speed (X) and Angle (Y)
  int x0 = 0, x1 = 0, y0 = 0, y1 = 0;
  // Loop for speed
  for (int i = 0; i < NUM_SPEEDS - 1; i++) {
    if (current_speed >= speed_bps[i] && current_speed <= speed_bps[i+1]) {
      x0 = i; x1 = i + 1; break; // If we find a match we can just break out
    }
  }
  // Loop for angle
  for (int j = 0; j < NUM_ANGLES - 1; j++) {
    if (current_angle >= angle_bps[j] && current_angle <= angle_bps[j+1]) {
      y0 = j; y1 = j + 1; break;
    }
  }

  // Calculate the interpolation weights (0.0 to 1.0)
  // Linear weight between the max delta of the higher and lower bounds
  float x_weight = (current_speed - speed_bps[x0]) / (speed_bps[x1] - speed_bps[x0]);
  float y_weight = (current_angle - angle_bps[y0]) / (angle_bps[y1] - angle_bps[y0]);

  // Interpolate along the X-axis for both Y0 and Y1
  float gain_y0 = gain_table[x0][y0] + x_weight * (gain_table[x1][y0] - gain_table[x0][y0]);
  float gain_y1 = gain_table[x0][y1] + x_weight * (gain_table[x1][y1] - gain_table[x0][y1]);

  // Interpolate along the Y-axis between the two resulting X-interpolations
  return gain_y0 + y_weight * (gain_y1 - gain_y0);
}

/* This function is the speed gain function that will command the motor to a specific angle based on the front wheel angle.
  The rear steer angle follows the same sign as the front (left is positive), i.e. if the gain is positive the rear steers
  in-phase and if the gain is negative then the rear steers counter-phase. */
void steer_speed_gain() {
  // CURRENT VERSION: Rear steering is directly proportional to the front with no gain.
  // steerAng should be between -1300 and 1300 approximately. This is angle in tenths of a degree
  // Rack moves 3.5 in/rev = 88.9 mm/rev 
  // thus 0.0112485939 rev/mm, mult by 12*pi to get 0.424062 rad/6mmS

  // Normalizes the steering between -1.0 and 1.0. A full negative lock will be -1 and a full positive lock will be 1
  float steerNormalized = constrain(steerAng, -1350, 1350)/1350.0f;
  float gain = 0.0;

  // ADD A CHECK FOR IF THE OVERRIDE PADDLES HAVE BEEN ACTUATED. IF SO AND IF MODE IS NOT OFF THEN IGNORE GAIN AND
  // COMMAND WHEELS TO ABSOLUTE PADDLE POSITION INSTEAD

  switch (mode) {
    case RWSMode::SPD_GAIN:
      gain = get_2d_gain(speed, steerNormalized);
      break;
    case RWSMode::FIXED_GAIN:
      gain = 0.1*fixed_gain;
      break;
    default: // OFF
      pack_send_ControlFrame(0,0,0,0,0);
      kp = 0.0;
      return; // Early return, no torque application
  }

  if (kp < target_kp) ramp_kp(); // Ramp kp slowly to not cause a snap after honing

  float target_pos = HOME + steerNormalized*gain*0.424062; // Command the steering to its relative position within the lock

  pack_send_ControlFrame(target_pos, 0.0, kp, kd, 0.0);
}

void setup() {
  Serial.begin(115200);
  delay(3000); 

  pinMode(PIN_CAN_STANDBY, OUTPUT);
  digitalWrite(PIN_CAN_STANDBY, LOW); 

  pinMode(HONE_PIN, INPUT_PULLUP); // DOUBLE CHECK THIS

  SPI.begin(); 

  // 16MHz is correct for the Adafruit CAN Feather
  ACAN2515Settings settings(16UL * 1000UL * 1000UL, 1000UL * 1000UL);
  const uint16_t errorCode = can.begin(settings, [] { can.isr(); });

  if (errorCode != 0) {
    while (1) {
      Serial.print("Error Initializing MCP2515: ");
      Serial.println(errorCode);
      delay(1000); 
    }
  }

  Serial.println("Sending Exit Command (Clearing states)...");
  CANMessage controlMsg;
  controlMsg.id = MOTOR_CAN_ID;
  controlMsg.ext = false; 
  controlMsg.len = 8;

  memcpy(controlMsg.data, MIT_EXIT, 8);
  can.tryToSend(controlMsg);
  delay(100); 

  Serial.println("Setting Current Position as Zero...");
  memcpy(controlMsg.data, MIT_ZERO, 8);
  can.tryToSend(controlMsg);
  delay(100); // Give encoder time to reset coordinates

  Serial.println("Sending Enter Command (Enabling)...");
  memcpy(controlMsg.data, MIT_ENTER, 8);
  can.tryToSend(controlMsg);

  /* Commented out to enable manual honing
  if (!hone_find_center()) {
    pack_send_ControlFrame(0.0, 0.0, 0.0, 0.0, 0.0);
    exit(-1); // Error
  }
  */
}

void loop() {
  // Safe Mode: Pos 0, Vel 0, Kp 0 (Zero Stiffness), Kd 0 (Zero Damping), Torque 0
  // This satisfies the watchdog and triggers telemetry without moving the motor.
  // pack_send_ControlFrame(0.0, 0.0, 0.0, 0.0, 0.0); // THIS LINE IS SAFE MODE
  // test_SINEWAVE(); // Oscillates in a 0.8 radian total rotation sine wave pattern.
  static uint32_t last_time = 0;
  CANMessage rxMsg;
  while (can.receive(rxMsg)) { // Unpack all CAN messages
    switch (rxMsg.id) {
      case MOTOR_CAN_ID:
        unpack_TelemetryFrame(rxMsg.data);
        motor_last_seen = millis();
        break;
      case 0x242:
        mode = static_cast<RWSMode>(rxMsg.data[0]);
        fixed_gain = static_cast<int8_t>(rxMsg.data[1]);
        break;
      case 0x640:
        rpm = static_cast<uint16_t>(
          (static_cast<uint16_t>(rxMsg.data[0]) << 8) |
          static_cast<uint16_t>(rxMsg.data[1])
        );
        break;
      case 0x656:
        steerAng = static_cast<int16_t>(
            (static_cast<uint16_t>(rxMsg.data[0]) << 8) |
            static_cast<uint16_t>(rxMsg.data[1])
        );
        break;
      case 0x659:
        speed = static_cast<int16_t>(
            (static_cast<uint16_t>(rxMsg.data[4]) << 8) |
            static_cast<uint16_t>(rxMsg.data[5])
        ) / 10.0f;
        break;
      default:
        break;
    } 
  }

  uint32_t current_time = millis();
  if (current_time - motor_last_seen > 250) {
    is_honed = false; 
  }

  if (digitalRead(HONE_PIN) == LOW && !is_honed && rpm == 0) { // REPLACE FALSE HERE WITH THE PIN BEING USED FOR THE HONE BUTTON
    is_honed = hone_find_center();
    // Reset the global kp to 0.0 here so the ramp_kp() function 
    // provides a smooth transition when handing control back to the driver
    if (is_honed) kp = 0.0; 
  }

  if (current_time - last_time >= 10) { // Run at 100Hz
    last_time = current_time;
    if (is_honed) {
      steer_speed_gain(); // Call steering function
    } else {
      pack_send_ControlFrame(0.0, 0.0, 0.0, 0.0, 0.0); // FLOPPY MODE
    }
  }
}