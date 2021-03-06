# You need to install pyaudio to run this example
# pip install pyaudio

# When using a microphone, the AudioSource `input` parameter would be
# initialised as a queue. The pyaudio stream would be continuosly adding
# recordings to the queue, and the websocket client would be sending the
# recordings to the speech to text service


import pyaudio
from ibm_watson import SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource
from threading import Thread
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
try:
    from Queue import Queue, Full
except ImportError:
    from queue import Queue, Full
import RPi.GPIO as GPIO
from time import sleep

SERVO_PIN = 12
KEYWORDS_LIST = ['sorry', 'dumb', 'did that make sense', 'i just', 'i\'m no expert', 'i think', 'i feel like', 'i\'m not very good', 'i am not very good']
CHUNK = 1024
BUF_MAX_SIZE = CHUNK * 10
q = Queue(maxsize=int(round(BUF_MAX_SIZE / CHUNK)))
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000

# GPIO Setup
def setup_servo():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    pwm = GPIO.PWM(SERVO_PIN, 50)
    pwm.start(0)

def set_angle(angle):
    duty = angle / 18 + 2
    GPIO.output(12, True)
    pwm.ChangeDutyCycle(duty)
    sleep(1)
    GPIO.output(12, False)
    pwm.ChangeDutyCycle(0)

setup_servo()
set_angle(0)

# Audio setup
audio_source = AudioSource(q, True, True)

# Watson setup
authenticator = IAMAuthenticator(API_KEY)
speech_to_text = SpeechToTextV1(authenticator=authenticator)

# define callback for the speech to text service
class MyRecognizeCallback(RecognizeCallback):
    def __init__(self):
        RecognizeCallback.__init__(self)

    def on_connected(self):
        print('Connection was successful')

    def on_error(self, error):
        print('Error received: {}'.format(error))

    def on_inactivity_timeout(self, error):
        print('Inactivity timeout: {}'.format(error))

    def on_listening(self):
        print('Service is listening')

    def on_data(self, data):
        if (data['results'][0]['final']): # if end of sentence
            text = data['results'][0]['alternatives'][0]['transcript'].lower()
            for keyword in KEYWORDS_LIST:
                if keyword in text:
                    set_angle(180)
                    set_angle(0)

    def on_close(self):
        print("Connection closed")

# this function will initiate the recognize service and pass in the AudioSource
def recognize_using_weboscket(*args):
    mycallback = MyRecognizeCallback()
    speech_to_text.recognize_using_websocket(audio=audio_source,
                                             content_type='audio/l16; rate=44100',
                                             recognize_callback=mycallback,
                                             interim_results=True)


# define callback for pyaudio to store the recording in queue
def pyaudio_callback(in_data, frame_count, time_info, status):
    try:
        q.put(in_data)
    except Full:
        pass # discard
    return (None, pyaudio.paContinue)

# instantiate pyaudio
audio = pyaudio.PyAudio()

def list_devices():
    """List all available microphone devices."""
    try:
        import pyaudio
    except ImportError:
        print("You have to install extra 'sound' in order to use this shell script")
        return 99

    pa = pyaudio.PyAudio()
    for i in range(pa.get_device_count()):
        dev = pa.get_device_info_by_index(i)
        input_chn = dev.get('maxInputChannels', 0)
        if input_chn > 0:
            name = dev.get('name')
            rate = dev.get('defaultSampleRate')
            print("Index {i}: {name} (Max Channels {input_chn}, Default @ {rate} Hz)".format(
                i=i, name=name, input_chn=input_chn, rate=int(rate)

            ))
    return 0

list_devices()

# open stream using callback
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
    input_device_index=2,
    stream_callback=pyaudio_callback,
    start=False
)

print("Enter CTRL+C to end recording...")
stream.start_stream()

try:
    recognize_thread = Thread(target=recognize_using_weboscket, args=())
    recognize_thread.start()

    while True:
        pass
except KeyboardInterrupt:
    # stop recording
    stream.stop_stream()
    stream.close()
    audio.terminate()
    audio_source.completed_recording()