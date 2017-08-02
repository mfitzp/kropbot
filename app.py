import os
import time

from flask import Flask
from flask_socketio import SocketIO, join_room

app = Flask(__name__)
app.config.from_object(os.environ.get('APP_SETTINGS', 'config.Config'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = app.config['SECRET_KEY']
socketio = SocketIO(app)

# Use a secret WS endpoint for robot.
robot_ws_secret = app.config['ROBOT_WS_SECRET']

# Buffer incoming instructions and emit direct to the robot.
# on each image cycle.
instruction_buffer = {}
latest_robot_state = {}

INSTRUCTION_DURATION = 3


@app.route('/')
def index():
    """
    Return template for survey view, data (form) loaded by JSON
    :return: raw index.html response
    """
    return app.send_static_file('index.html')


def clear_expired_instructions():
    """
    Remove all expired instructions from the buffer.

    Instructions are expired if their age > INSTRUCTION_DURATION. This needs to be low
    enough that the robot stops performing a behaviour when a client leaves, but
    high enough that an active client's instructions are not cleared due to lag.
    """
    global instruction_buffer
    threshold = time.time() - INSTRUCTION_DURATION
    instruction_buffer = {k: v for k, v in instruction_buffer.items() if v['timestamp'] > threshold}


@socketio.on('client_ready')
def client_ready_join_room(message):
    """
    Receive the ready instruction from (browser) clients and assign them to the client room.
    """
    join_room('clients')


@socketio.on('instruction')
def user_instruction(message):
    """
    Receive and buffer direction instruction from client.
    :return:
    """

    # Perform validation on inputs, direction must be in range 1-9 or None. Anything else
    # is interpreted as None (=STOP) from that client.
    message['direction'] = message['direction'] if message['direction'] in range(1, 9) else None

    instruction_buffer[message['user']] = {
        'direction': message['direction'],
        'timestamp': int(time.time())
    }


@socketio.on('robot_update_' + robot_ws_secret)
def robot_update(message):
    """
    Receive the robot's current status message (dict) and store for future
    forwarding to clients. Respond with the current instruction buffer directions.
    :param message: dict of robot status
    :return: list of directions (all clients)
    """
    # Forward latest state to clients.
    socketio.emit('updated_status', message, json=True, room='clients')
    # Clear expired instructions and return the remainder to the robot.
    clear_expired_instructions()
    return [v['direction'] for v in instruction_buffer.values()]


@socketio.on('robot_image_' + robot_ws_secret)
def robot_image(data):
    """
    Receive latest image data and broadcast together with
    the latest robot state.
    :param data:
    """
    # Forward latest camera image
    socketio.emit('updated_image', data, room='clients')


if __name__ == '__main__':
    socketio.run(app)
