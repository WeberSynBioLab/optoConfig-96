#include<Arduino.h>

// TO UPLOAD TO THE OPTOPLATE:
// After copying the code into the Arduino IDE, make sure to select 'Arduino Micro'
// at Tools > Board. Also select the correct port at Tools > Port.
// Afterwards click the Upload button in the toolbar, or press Ctrl+U.


/* -----------------------------------------------------------------------------
Incorporate a modified version of the Adafruit TLC5947 library inline.
The original version uses the Arduino digitalWrite() function when writing new
LED intensities. This is slower than the lower-level instructions (approx.
60 ms original vs. 13 ms modified).

The downside is that the Pin numbers are now hardcoded:
_clk = 5
_dat = 4
_lat = 6


The original license text follows.
----------------------------------------------------------------------------- */

// BEGIN INCORPORATED LIBRARY

/***************************************************
  This is a library for our Adafruit 24-channel PWM/LED driver

  Pick one up today in the adafruit shop!
  ------> http://www.adafruit.com/products/1429

  These drivers uses SPI to communicate, 3 pins are required to
  interface: Data, Clock and Latch. The boards are chainable

  Adafruit invests time and resources providing this open source code,
  please support Adafruit and open-source hardware by purchasing
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.
  BSD license, all text above must be included in any redistribution
 ****************************************************/



class Adafruit_TLC5947 {
    private:
        uint8_t numdrivers, _clk, _dat, _lat;
        uint16_t* pwmbuffer = nullptr;


    public:
        Adafruit_TLC5947(uint8_t n) {
            numdrivers = n;
            _clk = 5; // C6
            _dat = 4; // D4
            _lat = 6; // D7

            pwmbuffer = (uint16_t *)calloc(2, 24*n);
        }

        void write(void) {
          PORTD &= ~_BV(PD4);
          // 24 channels per TLC5974
          for (int16_t c=24*numdrivers - 1; c >= 0 ; c--) {
            // 12 bits per channel, send MSB first
            for (int8_t b=11; b>=0; b--) {
              PORTC &= ~_BV(PC6);
              // digitalWrite(_clk, LOW);

              if (pwmbuffer[c] & (1 << b))
                PORTD |= _BV(PD4);
                // digitalWrite(_dat, HIGH);
              else
                PORTD &= ~_BV(PD4);
                // digitalWrite(_dat, LOW);

              PORTC |= _BV(PC6);
              // digitalWrite(_clk, HIGH);
            }
          }
          PORTC &= ~_BV(PC6);
          // digitalWrite(_clk, LOW);

          PORTD |= _BV(PD7);
          // digitalWrite(_lat, HIGH);
          PORTD &= ~_BV(PD7);
          // digitalWrite(_lat, LOW);
        }


        void setPWM(uint16_t chan, uint16_t pwm) {
          if (pwm > 4095) pwm = 4095;
          if (chan > 24*numdrivers) return;
          pwmbuffer[chan] = pwm;
        }


        void setLED(uint8_t lednum, uint16_t r, uint16_t g, uint16_t b) {
          setPWM(lednum*3, r);
          setPWM(lednum*3+1, g);
          setPWM(lednum*3+2, b);
        }


        bool begin() {
          if (!pwmbuffer) return false;

          pinMode(_clk, OUTPUT);
          pinMode(_dat, OUTPUT);
          pinMode(_lat, OUTPUT);
          digitalWrite(_lat, LOW);

          return true;
        }
};

// END INCORPORATED LIBRARY


const uint8_t N_TLC5947 = 12;
const uint8_t oe  = 7;  // set to -1 to not use the enable pin (its optional)

const uint8_t LED1 = 0;
const uint8_t LED2 = 1;
const uint8_t LED3 = 2;

// Plate configuration: 1-, 2-, or 3-color?
// OPTOPLATE_CONFIG_N_COLORS


Adafruit_TLC5947 tlc = Adafruit_TLC5947(N_TLC5947);


/*
    Set intensity of first LED.
    1-color plate: blue
    2-color plate: far red
    3-color plate: blue

    @params well The number of the well to set.
    @params intensity Intensity to set the LED to.
*/
void setLED1(uint8_t well, uint16_t intensity)
{
    uint16_t led1position = (uint16_t)((int)(well/12) + 8*(well%12));
    tlc.setPWM(led1position, intensity);
}


/*
    Set intensity of second LED.
    1-color plate: blue
    2-color plate: far red
    3-color plate: red

    @params well The number of the well to set.
    @params intensity Intensity to set the LED to.
*/
void setLED2(uint8_t well, uint16_t intensity)
{
    uint16_t led2position = (uint16_t)((int)(well/12) + 8*(well%12)+96);
    tlc.setPWM(led2position, intensity);
}


/*
    Set intensity of third LED.
    1-color plate: blue
    2-color plate: red
    3-color plate: far red

    @params well The number of the well to set.
    @params intensity Intensity to set the LED to.
*/
void setLED3(uint8_t well, uint16_t intensity)
{
    uint16_t led3position = (uint16_t)(well+192);
    tlc.setPWM(led3position, intensity);
}



/*
    Set intensity of an LED. Which drivers are addressed specifically depends
    on the plate color configuration.

    @params well The number of the well to set.
    @params color Index of the color to set.
    @params intensity Intensity to set the LEDs to.
*/
void set(uint8_t well, uint8_t color, uint16_t intensity)
{
    if (N_COLORS == 1)
    {
        set_1color(well, intensity);
    } else if (N_COLORS == 2)
    {
        set_2color(well, color, intensity);
    } else if (N_COLORS == 3)
    {
        set_3color(well, color, intensity);
    }
}


/*
    Set intensity for a well in the 1-color plate configuration.

    All three LEDs are blue LEDs. LED 1 and 2 are dimmed, because both drivers
    together deliver 60 mA, but the LED can handle 50 mA.

    @params well The number of the well to set.
    @params intensity Intensity to set the LEDs to.
*/
void set_1color(uint8_t well, uint16_t intensity)
{
    // At a setting of 4095, the blue LED connected to drivers 1+2 will receive
    // more than the 50 mA it is specified for. To prevent this, scale back the
    // intensity.
    uint16_t dimmed_int = (uint16_t)(intensity * float(3300.0/4095.0));
    setLED1(well, dimmed_int);
    setLED2(well, dimmed_int);
    setLED3(well, intensity);
}


/*
    Set intensity for a well in the 2-color plate configuration.

    LED1 and LED2 are far red.
    LED3 is red.

    @params well The number of the well to set.
    @params color Index of the color to set.
    @params intensity Intensity to set the LEDs to.
*/
void set_2color(uint8_t well, uint8_t color, uint16_t intensity)
{
    if (color == 0)
    {
        // red
        setLED3(well, intensity);
    } else if (color == 1)
    {
        // far red
        setLED1(well, intensity);
        setLED2(well, intensity);
    }
}


/*
    Set intensity for a well in the 3-color plate configuration.

    LED1 is blue.
    LED2 is red.
    LED3 is far red.

    @params well The number of the well to set.
    @params color Index of the color to set.
    @params intensity Intensity to set the LEDs to.
*/
void set_3color(uint8_t well, uint8_t color, uint16_t intensity)
{
    if (color == 0)
    {
        // blue
        setLED1(well, intensity);
    } else if (color == 1)
    {
        // red
        setLED2(well, intensity);
    } else if (color == LED3)
    {
        // far red
        setLED3(well, intensity);
    }
}


/*
    Set intensity of all LEDs.

    @params well The number of the well to set.
    @params intensity Intensity to set the LEDs to.
*/
void setAll(uint8_t well, uint16_t intensity)
{
    setLED1(well, intensity);
    setLED2(well, intensity);
    setLED3(well, intensity);
}


/*
    Set a bit in a byte array to 1.

    @params ar[] byte array
    @params position bit position of the bit to set.
*/
void bit_set(byte ar[], uint16_t position)
{
  uint8_t arr_idx = position / 8;
  uint8_t bit_idx = position % 8;
  ar[arr_idx] |= (1 << bit_idx);
}


/*
    Return true if a bit in a byte array is 1, false otherwise.

    @params ar[] byte array
    @params position bit position of the bit to read.
*/
bool bit_get(byte ar[], uint16_t position)
{
  uint8_t arr_idx = position / 8;
  uint8_t bit_idx = position % 8;
  return ((ar[arr_idx] & (1 << bit_idx)) != 0);
}


struct Step
{
    uint32_t duration;
    uint32_t pulse_on;
    uint32_t pulse_off;
    uint16_t intensity;
};

// Step storage:
// Store steps as byte arrays of exactly the size needed to store all parameters.
// This avoids storing all steps with the largest data type, saving space.
// The first byte has to hold the size information to allow reading the data later.

// OPTOPLATE_CONFIG_STEPS


// Definition of programs

// OPTOPLATE_CONFIG_PROGRAMS

// OPTOPLATE_CONFIG_N_ADVANCED_ARR_SIZE

// Program IDs assigned to each well and color

// OPTOPLATE_CONFIG_WELLS


// Correction factors for each LED, rescaled from [0.0, 1.0] to [0, 65535]

// OPTOPLATE_CONFIG_CORRECTION_FACTORS

// At which time did the current step start?
uint32_t PROGS_CUR_STEP_T[288] = {0};
// Which is the index of the currently running step in the program?
uint8_t PROGS_CUR_STEP_N[288] = {0};


/*
    Returns the program ID associated with a well and a color.

    @param well The index of the well.
    @param color The index of the color (0, 1 or 2).
*/
uint16_t get_program_id(uint8_t well, uint8_t color)
{
    uint16_t program_id = pgm_read_word_near(&(PROGRAM_IDS[well][color]));
    return program_id;
}


/*
    Returns the number of steps in a program.

    @param program_id The ID of the program.
*/
uint8_t get_program_size(uint16_t program_id)
{
  uint8_t program_size = pgm_read_byte_near(&(PROGRAM_SIZES[program_id]));
  return program_size;
}


/*
    Returns a pointer to the byte array in PROGMEM which stores a Step in a program.

    @params program_id The ID of the program.
    @params step_n Position of the Step in the program (index in the program array)
*/
const byte* const get_step_ptr(uint16_t program_id, uint8_t step_n)
{
    const byte* const* prog_ptr = pgm_read_word_near(PROGRAMS + program_id);
    const byte* const step_ptr = pgm_read_word_near(prog_ptr + step_n);
    return step_ptr;
}


/*
    Returns the number of bytes corresponding to a size code.
    See optoConfig96.export of the GUI program for definition of codes.
    0: 1 byte, 1: 2 bytes, 2: 4 bytes

    @param code The size code
*/
uint8_t code2size(uint8_t code)
{
    switch (code)
    {
        case 0: return 1;
        case 1: return 2;
        case 2: return 4;
        default: return 0;
    }
}

/*
    Returns a Step after reading it from PROGMEM.

    @param step_ptr Pointer to the first byte of the step.
*/
struct Step get_step(const byte* const step_ptr)
{
    // Maximum bytes per step are 15. Copy all from PROGMEM to prevent multiple
    // (slow) read accessions, then only use what's neccessary.
    byte step_bytes[15] = {0};
    memcpy_P(&step_bytes, step_ptr, 15);

    // The first byte of the step holds size information about the parameters
    uint8_t size_byte = step_bytes[0];

    // Extract the size codes for Step members and get their byte size
    uint8_t size_dur = code2size((size_byte & 0b11000000) >> 6);
    uint8_t size_on  = code2size((size_byte & 0b00110000) >> 4);
    uint8_t size_off = code2size((size_byte & 0b00001100) >> 2);
    uint8_t size_inten = code2size((size_byte & 0b00000011));

    struct Step step = {0};

    // Actual data for the step begins at the second byte
    byte* s = step_bytes + 1;
    memcpy(&step.duration,  s, size_dur);
    memcpy(&step.pulse_on,  s + size_dur, size_on);
    memcpy(&step.pulse_off, s + size_dur + size_on, size_off);
    memcpy(&step.intensity, s + size_dur + size_on + size_off , size_inten);
    return step;
}


/*
    Returns the currently running Step of a program.

    @params program_id The ID of the program.
*/
struct Step get_cur_step(uint16_t program_id)
{
    uint8_t cur_step_n = get_cur_step_n(program_id);
    return get_step(get_step_ptr(program_id, cur_step_n));
}


/*
    Returns the duration of a Step.

    Multiple durations are needed to calculate whether a Program must advance to the next Step.
    It is faster to only get the duration, instead of the whole Step.

    @param step_ptr Pointer to the first byte of the step.
*/
uint32_t get_step_duration(const byte* const step_ptr)
{
    // Maximum bytes for a step duration are 5 (1 byte size_byte + 4 byte duration).
    byte step_bytes[5] = {0};
    memcpy_P(&step_bytes, step_ptr, 5);

    uint8_t size_byte = step_bytes[0];
    uint32_t size_dur = code2size((size_byte & 0b11000000) >> 6);

    uint32_t dur = 0;
    memcpy(&dur, step_bytes + 1, size_dur);

    return dur;
}


/*
    Returns the position of the Step in the program (index in the program array).

    @param program_id The ID of the program.
*/
uint8_t get_cur_step_n(uint16_t program_id)
{
    return PROGS_CUR_STEP_N[program_id];
}


/*
    Returns the starting time of the current step in a program.

    @param program_id The ID of the program.
*/
uint32_t get_cur_step_start(uint16_t program_id)
{
    return PROGS_CUR_STEP_T[program_id];
}


/*
    Returns `true` if a Step is ON at given time, `false` otherwise.

    @param step The step for which to check state.
    @param cur_millis Time at which to check.
    @program_id The ID of the program the Step is a part of.
*/
bool is_on(struct Step &step, uint32_t &cur_millis, uint16_t program_id)
{
    uint32_t t_stepstart = get_cur_step_start(program_id);
    uint32_t t_step = cur_millis - t_stepstart;

    // Edge cases:
    if (step.pulse_on == 0 && step.pulse_off == 0)
    {
        // ON is 0 and OFF is 0: not pulsed, always on
        return true;
    } else if  (step.pulse_on == 0 && step.pulse_off > 0)
    {
        // Only ON is 0: always off
        return false;
    } else if (step.pulse_off == 0 && step.pulse_on > 0)
    {
        // Only OFF is 0: always on
        return true;
    }

    uint32_t cycle = (uint32_t)(t_step / (step.pulse_on + step.pulse_off));
    if (t_step < (step.pulse_on + step.pulse_off) * cycle + step.pulse_on)
    {
        return true;
    }
    else
    {
        return false;
    }
}


/*
    Perform necessary operations to advance the step and return if the
    program was advanced to the next step.

    @params cur_millis Current run time.
    @params program_id The ID of the program.
*/
bool advance_step(uint32_t &cur_millis, uint16_t program_id)
{
    uint8_t step_n = get_cur_step_n(program_id);
    uint8_t program_size = get_program_size(program_id);
    const byte* const cur_step_ptr = get_step_ptr(program_id, step_n);
    uint32_t next_start = get_cur_step_start(program_id) + get_step_duration(cur_step_ptr);

    if (step_n == program_size - 1)
    {
        // End of the program was reached
        return false;
    }

    if (next_start >= cur_millis)
    {
        // No step advancement yet
        return false;
    }

    // Step advancement is necessary
    while (step_n + 1 < program_size)
    {
        // Loop until we reach the end of the program, or the start of the next
        // Step is in the future
        // Should we ever miss a Step in between, this will catch up again
        step_n++;
        PROGS_CUR_STEP_N[program_id] = step_n;
        PROGS_CUR_STEP_T[program_id] = next_start;
        const byte* const next_step_ptr = get_step_ptr(program_id, step_n);
        next_start = get_cur_step_start(program_id) + get_step_duration(next_step_ptr);
        // Check if we missed a step: If so, catch up, else break the loop and
        // report the step advancement
        if (next_start >= cur_millis)
        {
            break;
        }
    }
    return true;
}


/*
    Correct LED intensity setting by a correction factor and return the result.

    @params intensity Intensity setting before correction
    @params well Index of the well.
    @params corr_fctr_ptr Pointer to the relevant correction matrix.
*/
uint16_t correct_intensity(uint16_t intensity, uint8_t well, const uint16_t* const corr_fctr_ptr)
{
    uint16_t corr_fctr = pgm_read_word_near(&corr_fctr_ptr[well]);
    // Correction factors are rescaled to 16bit integers for storage, use
    // float for calculation.
    float corr_fctr_float = (float) corr_fctr / 65535;
    uint16_t new_int = (uint16_t) ((float)intensity * corr_fctr_float);
    return new_int;
}


/*
    Blink the internal LED after all steps have run at least once.
*/
void blink_builtin()
{
    static bool s_led_state = false;
    if (s_led_state)
    {
        digitalWrite(LED_BUILTIN, LOW);
        s_led_state = false;
    } else
    {
        digitalWrite(LED_BUILTIN, HIGH);
        s_led_state = true;
    }
}


void setup()
{
    Serial.begin(9600);
    tlc.begin();

    //set initial LED states to 0
    for (int well = 0; well < 96; well++)
    {
        setAll(well,0);
    }

    tlc.write();

    if (oe >= 0)
    {
        pinMode(oe, OUTPUT);
        digitalWrite(oe, HIGH);
    }

    // Configure optoPlate hardware:
    // Currently, only sets fan speed.

    // OPTOPLATE_CONFIG_HARDWARE

    // Initially, set internal LED to on.
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);
}


void loop()
{

    // At which time point did we last calculate anything?
    static uint32_t s_prev_millis = 0;

    // helper variable to set LED states on the first loop
    // Without it, the first pulse will be skipped, and unpulsed steps will never
    // turn on. This happens because 'advanced' is false, step_n remains 0.
    // cur_millis and s_prev_millis are both 0, so old_state == new_state.
    // Thus, the changed flag never gets set.
    static bool s_first_loop_over = false;

    // LED states are determined in loop (n-1), and written in loop (n),
    // thus keep the s_changed flag between loops.
    static bool s_changed = false;

    // Determine delay until the first loop runs and correct for it.
    static uint32_t s_delay = millis();
    uint32_t cur_millis = millis() - s_delay;

    if (s_first_loop_over && cur_millis - s_prev_millis < 100)
    {
        return;
    }

    if (s_changed) {
        tlc.write();
        s_changed = false;
    }

    // OPTOPLATE_CONFIG_DONE_AFTER : static const uint32_t s_done_after = N;
    if (cur_millis > s_done_after)
    {
        // Blink LEDs after all programs are done.
        blink_builtin();
    }

    byte prg_advanced[N_ADVANCED_ARR_SIZE] = {0};

    // During the first loop, set the advanced flag for all programs.
    if (!s_first_loop_over)
    {
        for (uint16_t i=0; i < N_PROGS; i++)
        {
            bit_set(prg_advanced, i);
        }
    }

    for (uint8_t well = 0; well < 96; well++)
    {
        for (uint8_t color = 0; color < N_COLORS; color++)
        {
            // Is there a change in intensity for this particular LED?
            bool this_changed = false;

            // Was the program associated with this LED advanced?
            bool this_advanced = false;

            uint16_t program_id = get_program_id(well, color);

            // Check if the current step of the current program was already
            // advanced for another LED, or needs to be advanced.
            if (bit_get(prg_advanced, program_id))
            {
                this_advanced = true;
                this_changed = true;
            } else if (advance_step(cur_millis, program_id))
            {
                this_advanced = true;
                this_changed = true;
                bit_set(prg_advanced, program_id);
            }

            struct Step cur_step = get_cur_step(program_id);

            // Check LED state now and at previous timepoint, but only if no
            // step advancement occurred. If the step was advanced, LED states
            // are no longer comparable between the current and previous time.

            // If the step was advanced, the starting state is ON by default.
            bool new_state = true;
            if (!this_advanced)
            {
                bool old_state = is_on(cur_step, s_prev_millis, program_id);
                new_state = is_on(cur_step, cur_millis, program_id);
                if (old_state != new_state)
                {
                    this_changed = true;
                }
            }

            uint16_t new_int = 0;
            if (new_state)
            {
                new_int = cur_step.intensity;
                // OPTOPLATE_CONFIG_PERFORM_INTENSITY_CORRECTION
            }

            if (this_changed)
            {
                set(well, color, new_int);
                s_changed = true;
            }

        }
    }
    s_prev_millis = cur_millis;
    s_first_loop_over = true;
}

