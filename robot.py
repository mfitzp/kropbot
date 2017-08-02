""""
Robot controller.

Runs on a Raspberry Pi Zero W, with Pi Motor HAT to interface with 2x
motors. A websocket is opened to the running control server (on Heroku)
to receive commands and send image updates. Images are sent on a regular
schedule (~5 per second). A second process pings the server with
the roboto status and the remote server will respond to each ping
with a set of updated instructions.

Instructions are received as a set of directions from all clients. These
are combined and used to calculate an average direction and magnitude.

"""

import atexit
from collections import Counter
from concurrent import futures
from io import BytesIO
import math, cmath
import os
import time

from Adafruit_MotorHAT import Adafruit_MotorHAT, Adafruit_DCMotor
from picamera import PiCamera
from socketIO_client import SocketIO

SPEED_MULTIPLIER = 200
UPDATES_PER_SECOND = 5
CAMERA_QUALITY = 10
CAMERA_FPS = 5

# A store of incoming instructions from clients, stored as list of client directions
instructions = []

# Use a secret WS endpoint for robot.
robot_ws_secret = os.getenv('ROBOT_WS_SECRET', '')

# Conversion from numeric inputs to motor instructions + multipliers. The multipliers
# are adjusted for each direction, e.g. forward is full-speed, turn is half.
DIRECTIONS = {
    1: ((Adafruit_MotorHAT.FORWARD, 0.75), (Adafruit_MotorHAT.FORWARD, 0.5)),
    2: ((Adafruit_MotorHAT.FORWARD, 0.5), (Adafruit_MotorHAT.BACKWARD, 0.5)),
    3: ((Adafruit_MotorHAT.BACKWARD, 0.75), (Adafruit_MotorHAT.BACKWARD, 0.5)),
    4: ((Adafruit_MotorHAT.BACKWARD, 1), (Adafruit_MotorHAT.BACKWARD, 1)),
    5: ((Adafruit_MotorHAT.BACKWARD, 0.5), (Adafruit_MotorHAT.BACKWARD, 0.75)),
    6: ((Adafruit_MotorHAT.BACKWARD, 0.5), (Adafruit_MotorHAT.FORWARD, 0.5)),
    7: ((Adafruit_MotorHAT.FORWARD, 0.5), (Adafruit_MotorHAT.FORWARD, 0.75)),
    8: ((Adafruit_MotorHAT.FORWARD, 1.5), (Adafruit_MotorHAT.FORWARD, 1.5)),
}

# Initialize motors, and define left and right controllers.
motor_hat = Adafruit_MotorHAT(addr=0x6f)
left_motor = motor_hat.getMotor(1)
right_motor = motor_hat.getMotor(2)


def turnOffMotors():
    """
    Shutdown motors and unset handlers.
    Called on exit to ensure the robot is stopped.
    """
    left_motor.run(Adafruit_MotorHAT.RELEASE)
    right_motor.run(Adafruit_MotorHAT.RELEASE)


def average_radians(list_of_radians):
    """
    Return average of a list of angles, in radians, and it's amplitude.

    We calculate a set of vectors for each angle, using a fixed distance.
    Add up the sum of the x, y of the resulting vectors.
    Work back to an angle + get a magnitude.

    :param list_of_radians:
    :return:
    """
    vectors = [cmath.rect(1, angle) if angle is not None else cmath.rect(0, 0)
               # length 1 for each vector; or 0,0 for null (stopped)
               for angle in list_of_radians]

    vector_sum = sum(vectors)
    return cmath.phase(vector_sum), abs(vector_sum)


def to_radians(d):
    """
    Convert 7-degrees values to radians.
    :param d:
    :return: direction in radians
    """
    return d * math.pi / 4 if d is not None else None


def to_degree7(r):
    """
    Convert radians to 'degrees' with a 0-7 scale.
    :param r:
    :return: direction in 7-value degrees
    """
    return round(r * 4 / math.pi)


def map1to8(v):
    """
    Limit v to the range 1-8 or None, with 0 being converted to 8 (straight ahead).

    This is necessary because the back-calculation to degree7 will negative values
    yet the input to calculate_average_instruction must use 1-8 to weight forward
    instructions correctly.
    :param v:
    :return: v, in the range 1-8 or None
    """
    if v is None or v > 0:
        return v
    return v + 8  # if 0, return 8


def calculate_average_instruction():
    """
    Return a dictionary of counts for each direction option in the current
    instructions and the direction with the maximum count.

    Directions are stored in numeric range 0-7, we first convert these imaginary
    degrees to radians, then calculate the average radians by adding vectors.
    Once we have that value in radians we can convert back to our own scale
    which the robot understands. The amplitude value gives us a speed.

    0 = Forward
    7/1 = Forward left/right (slight)
    6/2 = Turn left right (stationary)
    5/3 = Backwards left/right (slight)
    4 = Backwards

    :return: dict total_counts, direction
    """

    # If instructions remaining, calculate the average.
    if instructions:
        directions_v, direction_rads = zip(*[(d, to_radians(d)) for d in instructions])
        total_counts = Counter([map1to8(v) for v in directions_v])

        rad, magnitude = average_radians(direction_rads)

        if magnitude < 0.05:
            magnitude = 0
            direction = None

        return {
            'total_counts': total_counts,
            'direction': map1to8(to_degree7(rad)),
            'magnitude': magnitude
        }

    else:
        return {
            'total_counts': {},
            'direction': None,
            'magnitude': 0
        }


def control_robot(control):
    """
    Takes current robot control instructions and apply to the motors.
    If direction is None, all-stop, otherwise calculates a speed
    for each motor using a combination of DIRECTIONS, magnitude
    and SPEED_MULTIPLIER, capped at 255.
    :param control:
    """
    if control['direction'] is None:
        # All stop.
        left_motor.setSpeed(0)
        right_motor.setSpeed(0)
        return

    direction = int(control['direction'])
    left, right = DIRECTIONS[direction]
    magnitude = control['magnitude']

    left_motor.run(left[0])
    left_speed = int(left[1] * magnitude * SPEED_MULTIPLIER)
    left_speed = min(left_speed, 255)
    left_motor.setSpeed(left_speed)

    right_motor.run(right[0])
    right_speed = int(right[1] * magnitude * SPEED_MULTIPLIER)
    right_speed = min(right_speed, 255)
    right_motor.setSpeed(right_speed)


def on_new_instruction(message):
    """
    Handler for incoming instructions from clients. Instructions are received, combined
    and expired on the server, so only active instructions (on per client) are received
    here.
    :param message: dict of all current instructions from all clients.
    :return:
    """
    instructions.extend(message)
    print(int(time.time()), message)


def streaming_worker():
    """
    A self-container worker for streaming the Pi camera over websockets to the server
    as JPEG images. Initializes the camera, opens the websocket then enters a continuous
    capture loop, with each snap transmitted.
    :return:
    """
    camera = PiCamera()
    camera.resolution = (200, 300)
    camera.framerate = CAMERA_FPS

    with BytesIO() as stream, SocketIO('https://kropbot.herokuapp.com', 443) as socketIO:
        # capture_continuous is an endless iterator. Using video port + low quality for speed.
        for _ in camera.capture_continuous(stream, format='jpeg', use_video_port=True, quality=CAMERA_QUALITY):
            stream.truncate()
            stream.seek(0)
            data = stream.read()
            socketIO.emit('robot_image_' + robot_ws_secret, bytearray(data))
            stream.seek(0)


if __name__ == "__main__":
    # Register our function to disable motors when we shutdown.
    atexit.register(turnOffMotors)
    with futures.ProcessPoolExecutor() as executor:
        # Execute our camera streamer 'streaming_worker' in a separate process.
        # This runs continuously until exit.
        future = executor.submit(streaming_worker)

        with SocketIO('https://kropbot.herokuapp.com', 443) as socketIO:
            while True:
                current_time = time.time()
                lock_time = current_time + 1.0 / UPDATES_PER_SECOND
                # Calculate current average instruction based on inputs,
                # then perform the action.
                instruction = calculate_average_instruction()
                control_robot(instruction)
                instruction['n_controllers'] = len(instructions)
                # on_new_instruction is a callback to handle the server's response.
                socketIO.emit('robot_update_' + robot_ws_secret, instruction, on_new_instruction)
                # Empty all current instructions before accepting any new ones,
                # ensuring that if we lose contact with the server we stop.
                del instructions[:]
                socketIO.wait_for_callbacks(5)

                # Throttle the updates sent out to UPDATES_PER_SECOND (very roughly).
                time.sleep(max(0, lock_time - time.time()))
