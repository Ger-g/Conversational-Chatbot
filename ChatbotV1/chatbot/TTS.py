# Copyright 2017 Bo Shao. All Rights Reserved.
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
import pyttsx3

engine = pyttsx3.init()
engine.setProperty('rate',110)  #120 words per minute
engine.setProperty('volume',0.9)
engine.say("Hi, my name is fuck-face, talk to me once you see the chat arrow.")
engine.runAndWait()

print('2')
engine.say("Well, fuck me in my big fat sweaty asshole")
engine.runAndWait()