# Copyright 2017 Bo Shao. & Greg Summmers All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
from __future__ import division
import os
import re
import sys

import numpy as np
import collections
import time

from firebase import firebase
import tensorflow as tf
import grpc

import pyttsx3
import pyaudio

from settings import PROJECT_ROOT
from chatbot.botpredictor import BotPredictor

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from six.moves import queue

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

fbase = firebase.FirebaseApplication('https://testing-27640.firebaseio.com/', authentication=None)

# statuses
mic_rec = True
talkTime = False
ttStart = None

def duration_to_secs(duration):
    return duration.seconds + (duration.nanos / float(1e9))

class MicrophoneStream():
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk_size):
        self._rate = rate
        self._chunk_size = chunk_size

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

        # Some useful numbers
        self._num_channels = 1  # API only supports mono for now

    def __enter__(self):
        self.closed = False

        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=self._num_channels, rate=self._rate,
            input=True, frames_per_buffer=self._chunk_size,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer)

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, *args, **kwargs):
        if mic_rec is True:
            """Continuously collect data from the audio stream, into the buffer."""
            self._buff.put(in_data)
        else:
            self._buff.put(np.zeros(400).tostring())

        return None, pyaudio.paContinue

    def generator(self):
        try:
            while not self.closed:
                # Use a blocking get() to ensure there's at least one chunk of
                # data, and stop iteration if the chunk is None, indicating the
                # end of the audio stream.
                chunk = self._buff.get()
                # if chunk is None:
                #     return
                data = [chunk]

                # Now consume whatever other data's still buffered.
                while True:
                    try:
                        chunk = self._buff.get(block=False)
                        if chunk is None:
                            return
                        data.append(chunk)
                    except queue.Empty:
                        break

                yield b''.join(data)
        except TypeError:
            print('\n Closing microphone')
            os._exit(0)

class ResumableMicrophoneStream(MicrophoneStream):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk_size, max_replay_secs=5):
        super(ResumableMicrophoneStream, self).__init__(rate, chunk_size)
        self._max_replay_secs = max_replay_secs

        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk_size * self._bytes_per_sample)
        self._chunks_per_second = int(self._bytes_per_second / self._bytes_per_chunk)
        self._untranscribed = collections.deque(maxlen=self._max_replay_secs * self._chunks_per_second)

    def on_transcribe(self, end_time):
        while self._untranscribed and end_time > self._untranscribed[0][1]:
            self._untranscribed.popleft()

def listen_audio_loop(responses):
    """
        Endpoint for our stream.
        A 'responses' generator - fed by Google Speech API - is parsed for various information.
        Once a response is final, it is cleaned and then sent to our predictor model.
    """
    num_chars_printed = 0
    global talkTime, ttStart
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        top_alternative = result.alternatives[0]
        transcript = top_alternative.transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if ttStart != None:
            # print(int(time.time() - ttStart))
            if (time.time() - ttStart) >= 10:
                talkTime = False

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()
            num_chars_printed = len(transcript)

        # Handler for a final result
        elif re.search(r'\b(Maverick)\b', transcript, re.I) or talkTime:
            talkTime = True
            ttStart = time.time()

            # cut mic
            global mic_rec
            mic_rec = False

            # Remove bot name if used as a wake word
            temp = transcript[1:8]
            if temp is 'Maverick':
                transcript = transcript[8:]

            print('You:  ', transcript)
            res = respond(transcript)

            # Exit recognition if transcription finds our keywords
            if re.search(r'\b(goodbye|quit)\b', transcript, re.I):
                print('Exiting..')
                post = transcript + "\n" + res
                fbase.post('/messages', {'message': post})
                sys.exit(0)
                # os._exit(0)

            # firebase
            post = transcript + "\n" + res
            fbase.post('/messages', {'message': post})

            # open mic, resume loop
            mic_rec = True
            sys.stdout.write("> Say something!")
            sys.stdout.flush()
            num_chars_printed = 0


def _record_keeper(responses, stream):
    """Calls the stream's on_transcribe callback for each final response.
    Args:
        responses - a generator of responses. The responses must already be
            filtered for ones with results and alternatives.
        stream - a ResumableMicrophoneStream.
    """
    try:
        for r in responses:
            result = r.results[0]
            if result.is_final:
                # Display the transcription of the top alternative.
                top_alternative = result.alternatives[0]
                transcript = top_alternative.transcript

                # Keep track of what transcripts we've received, so we can resume
                # intelligently when we hit the deadline
                stream.on_transcribe(duration_to_secs(top_alternative.words[-1].end_time))

            yield r
    except IndexError:
        print('\nINPUT_STREAM flushing...')
        miniMain()
        pass


def respond(Hsent):
    while Hsent:
        # Check to see if the user quits
        if Hsent.strip() == 'quit' or Hsent.strip() == 'goodbye':
            engine.say('It\'s been fun chatting with you, goodbye!')
            engine.runAndWait()
            os._exit(0)

        # Get the response from our NMT model
        ans = predictor.predict(Hsent)
        print('Bot:  ', ans)
        engine.say(ans)
        engine.runAndWait()
        sys.stdout.flush()

        return ans

# main loop used to re-initialize Google Speech Streaming Recognition
def miniMain():
    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=language_code,
        max_alternatives=1,
        enable_word_time_offsets=True)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)
    print("INPUT_STREAM ready")

    sys.stdout.write("> Say something!")
    sys.stdout.flush()

    with ResumableMicrophoneStream(16000, int(16000 / 10)) as stream:
        while True:
            # create audio stream from pyaudio, pipe it into Google Speech API, and get a transcript generator
            audio_generator = stream.generator()
            requests = (types.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
            responses = client.streaming_recognize(streaming_config, requests)

            try:
                # send the transcript generator to a listener loop
                listen_audio_loop(_record_keeper(responses, stream))
                break
            # Handler for: Mic open too long on a single Google API stream / Microphone is closed or is cycling
            except grpc.RpcError as e:
                if e.code() not in (grpc.StatusCode.INVALID_ARGUMENT, grpc.StatusCode.OUT_OF_RANGE):
                    raise
                details = e.details()
                if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                    if 'deadline too short' not in details:
                        raise
                else:
                    raise
                print('\nSwapping INPUT_STREAM...')

if __name__ == "__main__":
    # init TF chatbot params
    corp_dir = os.path.join(PROJECT_ROOT, 'Data', 'Corpus')
    knbs_dir = os.path.join(PROJECT_ROOT, 'Data', 'KnowledgeBase')
    res_dir = os.path.join(PROJECT_ROOT, 'Data', 'Result')
    language_code = 'en-US'  # a BCP-47 language tag

    # init TTS engine
    engine = pyttsx3.init()
    engine.setProperty('rate', 190)  # 120 words per minute
    engine.setProperty('volume', 1)
    engine.say("Hi, I'm Maverick.")
    engine.runAndWait()

    # init TF session  (Run other option to see connected components)
    # with tf.Session(config=tf.ConfigProto(log_device_placement=True)) as sess:
    with tf.Session(config=tf.ConfigProto()) as sess:
        predictor = BotPredictor(sess, corpus_dir=corp_dir, knbase_dir=knbs_dir, result_dir=res_dir,
                                 result_file='basic')
        while True:
            miniMain()
