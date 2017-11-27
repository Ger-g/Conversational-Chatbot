
import pyttsx3 as ts
import time

# init TTS engine
engine = ts.init()
engine.setProperty('rate', 190)  # 120 words per minute
engine.setProperty('volume', 1)
engine.say("Hello, nice day")
engine.runAndWait()

time.sleep(2.5)
engine.say("tell me a story")
engine.runAndWait()