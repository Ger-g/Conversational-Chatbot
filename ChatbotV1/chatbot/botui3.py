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

import argparse
import os
import re
import sys

import numpy as np
import threading
import collections
import time

from firebase import firebase
import tensorflow as tf
import grpc

import pyttsx3
import pyaudio

from settings import PROJECT_ROOT
from chatbot.botpredictor import BotPredictor
import chatbot.transcribe_streaming_mic as transcribe_streaming_mic

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from six.moves import queue
import six

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

def duration_to_secs(duration):
    return duration.seconds + (duration.nanos / float(1e9))


class ResumableMicrophoneStream(transcribe_streaming_mic.MicrophoneStream):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk_size, max_replay_secs=5):
        super(ResumableMicrophoneStream, self).__init__(rate, chunk_size)
        self._max_replay_secs = max_replay_secs

        # Some useful numbers
        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk_size * self._bytes_per_sample)
        self._chunks_per_second = int(self._bytes_per_second / self._bytes_per_chunk)
        # print(self._max_replay_secs, )
        self._untranscribed = collections.deque(maxlen=self._max_replay_secs * self._chunks_per_second)

    def on_transcribe(self, end_time):
        print('untrans ', len(self._untranscribed))

        while self._untranscribed and end_time > self._untranscribed[0][1]:
            print('stowing trans        size: ', len(self._untranscribed))
            self._untranscribed.popleft()

    def generator(self, resume=False):
        total_bytes_sent = 0
        total_bytes_saved = 0
        if resume:
            # Make a copy, in case on_transcribe is called while yielding them
            catchup = list(self._untranscribed)
            print(catchup)
            # Yield all the untranscribed chunks first
            for chunk, _ in catchup:
                yield chunk

        for byte_data in super(ResumableMicrophoneStream, self).generator():
            # Populate the replay buffer of untranscribed audio bytes
            total_bytes_sent += len(byte_data)
            chunk_end_time = total_bytes_sent / self._bytes_per_second
            self._untranscribed.append((byte_data, chunk_end_time))

            yield byte_data


class SimulatedMicrophoneStream(ResumableMicrophoneStream):
    def __init__(self, audio_src, *args, **kwargs):
        super(SimulatedMicrophoneStream, self).__init__(*args, **kwargs)
        self._audio_src = audio_src

    def _delayed(self, get_data):
        total_bytes_read = 0
        start_time = time.time()

        chunk = get_data(self._bytes_per_chunk)

        while chunk and not self.closed:
            total_bytes_read += len(chunk)
            expected_yield_time = start_time + (
                    total_bytes_read / self._bytes_per_second)
            now = time.time()
            if expected_yield_time > now:
                time.sleep(expected_yield_time - now)

            yield chunk

            chunk = get_data(self._bytes_per_chunk)

    def _stream_from_file(self, audio_src):
        with open(audio_src, 'rb') as f:
            for chunk in self._delayed(
                    lambda b_per_chunk: f.read(b_per_chunk)):
                yield chunk

        # Continue sending silence - 10s worth
        trailing_silence = six.StringIO(
                b'\0' * self._bytes_per_second * 10)
        for chunk in self._delayed(trailing_silence.read):
            yield chunk

    def _thread(self):
        for chunk in self._stream_from_file(self._audio_src):
            self._fill_buffer(chunk)
        self._fill_buffer(None)

    def __enter__(self):
        self.closed = False

        threading.Thread(target=self._thread).start()

        return self

    def __exit__(self, type, value, traceback):
        self.closed = True

def _record_keeper(responses, stream):
    """Calls the stream's on_transcribe callback for each final response.
    Args:
        responses - a generator of responses. The responses must already be
            filtered for ones with results and alternatives.
        stream - a ResumableMicrophoneStream.
    """
    for r in responses:
        result = r.results[0]
        if result.is_final:

            transcribe_streaming_mic.mic_rec = False
            # Display the transcription of the top alternative.
            top_alternative = result.alternatives[0]
            transcript = top_alternative.transcript
            print('You:  ', transcript)
            res = respond(transcript)

            if re.search(r'\b(goodbye|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            # Keep track of what transcripts we've received, so we can resume
            # intelligently when we hit the deadline
            stream.on_transcribe(duration_to_secs(top_alternative.words[-1].end_time))

            transcribe_streaming_mic.mic_rec = True
            sys.stdout.write("> Say something!")
            sys.stdout.flush()
        yield r


def listen_print_loop(responses, stream):
    """Iterates through server responses and prints them.
    Same as in transcribe_streaming_mic, but keeps track of when a sent
    audio_chunk has been transcribed.
    """
    print(responses)
    with_results = (r for r in responses if (r.results and r.results[0].alternatives))
    print('res ', with_results)
    transcribe_streaming_mic.listen_print_loop(_record_keeper(with_results, stream))

def respond(Hsent):
    while Hsent:
        if Hsent.strip() == 'quit' or Hsent.strip() == 'goodbye':
            engine.say('It\'s been a pleasure chatting with you, goodbye!')
            engine.runAndWait()
            break

        # get the response from our NMT model
        ans = predictor.predict(Hsent)
        print('Bot:  ', ans)
        engine.say(ans)
        engine.runAndWait()
        sys.stdout.flush()

        return ans

def main(sample_rate, audio_src):
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-US'  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code=language_code,
        max_alternatives=1,
        enable_word_time_offsets=True)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    print("You can now chat with Hugo!")
    # Waiting from standard input.
    sys.stdout.write("> Say something!")
    sys.stdout.flush()

    if audio_src:
        mic_manager = SimulatedMicrophoneStream(audio_src, sample_rate, int(sample_rate / 10))
    else:
        mic_manager = ResumableMicrophoneStream(sample_rate, int(sample_rate / 10))

    with mic_manager as stream:
        resume = False
        while True:
            audio_generator = stream.generator(resume=resume)
            requests = (types.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)

            responses = client.streaming_recognize(streaming_config, requests)

            try:
                # Now, put the transcription responses to use.
                listen_print_loop(responses, stream)
                break
            except grpc.RpcError as e:
                if e.code() not in (grpc.StatusCode.INVALID_ARGUMENT,
                                    grpc.StatusCode.OUT_OF_RANGE):
                    raise
                details = e.details()
                if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                    if 'deadline too short' not in details:
                        raise
                    if 'Invalid audio content: too long' not in details:
                        raise
                else:
                    if 'maximum allowed stream duration' not in details:
                        raise

                print('\n               Swapping streams..')
                resume = True

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
    engine.say("Hi, I'm Hugo.")
    engine.runAndWait()

    # init TF session
    with tf.Session() as sess:
        predictor = BotPredictor(sess, corpus_dir=corp_dir, knbase_dir=knbs_dir, result_dir=res_dir, result_file='basic')

        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('--rate', default=16000, help='Sample rate.', type=int)
        parser.add_argument('--audio_src', help='File to simulate streaming of.')
        args = parser.parse_args()

        main(args.rate, args.audio_src)

    # old
    #     print("You can now chat with Chatbot!")
    #     # Waiting from standard input.
    #     sys.stdout.write("> Say something!")
    #     sys.stdout.flush()

        # begin streaming from the microphone
        # with MicrophoneStream(RATE, CHUNK) as stream:
        #     audio_generator = stream.generator()
        #     requests = (types.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
        #     # input stream of Google speech API response objects
        #     responses = client.streaming_recognize(streaming_config, requests)
        #
        #     # Now, put the transcription responses to use.
        #     conv_loop(responses)
#
#
# def conv_loop(resp):
#     # Take the response objeccts and parse them until a full sentence is retrieved
#     num_chars_printed = 0
#     for response in resp:
#         if not response.results:
#             continue
#
#         # The `results` list is a consecutive list of transcribed input. For streaming, we only care about
#         # the first result being considered, since once it's `is_final`, it
#         # moves on to considering the next utterance.
#         result = response.results[0]
#
#         if not result.alternatives:
#             continue
#
#         # Display the transcription of the top alternative.
#         transcript = result.alternatives[0].transcript
#
#         # Display interim results, but with a carriage return at the end of the
#         # line, so subsequent lines will overwrite them.
#         # If the previous result was longer than this one, we need to print
#         # some extra spaces to overwrite the previous result
#         overwrite_chars = ' ' * (num_chars_printed - len(transcript))
#
#         if not result.is_final:
#             # if the result is still being parsed for input
#             sys.stdout.write(transcript + overwrite_chars + '\r')
#             sys.stdout.flush()
#
#             num_chars_printed = len(transcript)
#
#         else:
#             # once a result is final, output the transcription, cut mic input, and call the response method
#             Human_sent = (transcript + overwrite_chars)
#             global mic_rec
#             mic_rec = False
#
#             print('You:  ', Human_sent)
#             Bot_response = respond(Human_sent)
#
#             # Exit recognition if any of the transcribed phrases could be
#             # one of our keywords.
#             if re.search(r'\b(goodbye|quit)\b', transcript, re.I):
#                 print('Exiting..')
#                 break
#
#             else:
#                 # send chat info to firebase
#                 post = Human_sent + "\n" + Bot_response
#                 f = firebase.FirebaseApplication('https://testing-27640.firebaseio.com/', authentication=None)
#                 f.post('/messages', {'message': post})
#
#
#             mic_rec = True
#             sys.stdout.write("> Say something!")
#             sys.stdout.flush()
#             num_chars_printed = 0
