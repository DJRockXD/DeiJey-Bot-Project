import speech_recognition as sr
import pyttsx3 as p
import logging
import threading
import time
import queue

import DeijeyGraphics

log = logging.getLogger('logger')  # get the main logger


class Speaker:
    sex = 0
    speech_rate = 0
    speaker = None

    def __init__(self, sex, speech_rate):
        self.sex = sex
        self.speech_rate = speech_rate

        self.speaker = p.init()
        self.speaker.setProperty("rate", self.speech_rate)
        self.speaker.setProperty("voice", self.speaker.getProperty("voices")[self.sex].id)

    def speak(self, text):
        self.speaker.say(text)
        self.speaker.runAndWait()


def listen_mic(microphone, speech_recognizer, audio, graphics_switch):
    audio.put(speech_recognizer.listen(microphone, timeout=None, phrase_time_limit=10))
    graphics_switch[0] = False


def from_mic(listening_graphics):
    rec = sr.Recognizer()
    graphics_switch = [True]
    audio = queue.Queue()

    with sr.Microphone() as source:
        rec.adjust_for_ambient_noise(source)
        threading.Thread(target=listen_mic, args=(source, rec, audio, graphics_switch)).start()

        DeijeyGraphics.visible(listening_graphics, True)
        while graphics_switch[0]:
            listening_graphics.update_idletasks()
            listening_graphics.update()
            time.sleep(0.01)

    DeijeyGraphics.visible(listening_graphics, False)
    listening_graphics.update_idletasks()
    listening_graphics.update()

    try:
        re = rec.recognize_google(audio.get())
        time.sleep(0.2)
        return re

    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        log.critical("Request error given, speech recognition operation failed.")
        log.critical(
            "Instructions: Reconnect to the internet. Otherwise, check the Google API key by following the Documentation: https://github.com/Uberi/speech_recognition/blob/master/reference/library-reference.rst#:~:text=To%20obtain%20your,raise%20this%20limit")
        return ""
    except TimeoutError:
        log.exception(
            "TimeoutError [WinError 10060] given; speech_recognition API failed to respond, likely due to bad internet connection.", exc_info=True)
        return ""
