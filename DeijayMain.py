import logging
import logging.handlers
import queue
import socket
import struct
import threading
import time
from logging.config import dictConfig

import select
import pyautogui
import mouse

import DeijeyGraphics
import mouseControl
import voiceOperator as VOp

KEYWORD = "dj"
SERVER_IP, PORT = socket.gethostbyname(socket.gethostname()), 4001


class ProtocolController:
    def __init__(self):
        self.protocol_recording = []
        self.protocol_recording_switches = {'protocol_recording': False,
                                            'protocol_save': False}


class RequestHandlerThread(threading.Thread):

    def __init__(self, request_queue, sock, timer, pcl_tracker, on_off_switch):
        super().__init__(daemon=True)
        self.noError = True
        self.job = None
        self.current_request = None
        self.request_queue = request_queue
        self.sock = sock
        self.timer = timer
        self.program_switch = on_off_switch
        self.pcl_tracker = pcl_tracker

    def run(self):
        """
        Matches requests to services in a queue.
        Follows up on the main function, as a thread.
        """

        while not self.request_queue.empty():
            self.job, self.current_request, self.noError = None, None, True

            self.current_request = self.request_queue.get()
            set_request = set(self.current_request.split(" "))  # sets are significantly faster at 'in' statements.
            logger.debug(f"request: {self.current_request}")
            logger.debug(f"Keywords: {set_request}")

            for key in self.keyword_sorter:
                keywords_match = True
                if isinstance(self.keyword_sorter[key], list):
                    for group in self.keyword_sorter[key]:
                        if not group.intersection(set_request):
                            keywords_match = False
                            break
                elif not self.keyword_sorter[key].intersection(set_request):
                    keywords_match = False

                if keywords_match:
                    logger.info(f'Request identified in services: {key}')
                    self.job = key
                    break

            if self.job:
                self.job(self)
            else:
                logger.warning(f"Apologies, unknown command: '{self.current_request}'.")
                self.noError = False

            if self.noError and self.pcl_tracker.protocol_recording_switches['protocol_recording']:
                logger.debug('Recording protocol henceforth...')
                if self.pcl_tracker.protocol_recording_switches['protocol_save']:
                    logger.debug('Received request to stop recording. Checking for errors:')
                    try:
                        protocol_entry = self.current_request.split(' as ')[1]
                        logger.debug('Successfully extracted protocol entry from sentence.')
                    except IndexError:
                        logger.warning('Stopped listening mid-sentence. Recording preserved')
                        continue
                    protocol_data = f'{protocol_entry}{self.pcl_tracker.protocol_recording}'
                    logger.debug(f'protocol data organized: {protocol_data}')
                    self.pcl_tracker.protocol_recording_switches = {item: False for (item, value) in
                                                                    self.pcl_tracker.protocol_recording_switches.items()}
                    logger.debug(f'FALSE??? {self.pcl_tracker.protocol_recording_switches}')
                    self.send_then_handle('svpc', protocol_data)
                    self.pcl_tracker.protocol_recording.clear()
                    logger.debug(f'FALSE??? {self.pcl_tracker.protocol_recording_switches}')

                elif self.job != self.start_rec_protocol.__func__ \
                        and self.job != self.execute_protocol.__func__ \
                        and self.job != self.save_location_entry.__func__ \
                        and self.job != self.speak_entries.__func__:
                    self.pcl_tracker.protocol_recording.append(self.current_request)
                    logger.debug(f"Appended request into the protocol recording: {self.pcl_tracker.protocol_recording}")

            self.request_queue.task_done()

        logger.debug(f"total execution time: {time.perf_counter() - self.timer}")
        logger.debug("Terminating thread.")

    def receive_from_server(self):
        packed_length = self.sock.recv(4)
        data_len = struct.unpack('i', packed_length)[0]
        logger.debug('About to receive data from server:')
        chunk = self.sock.recv(data_len)
        logger.debug('Confirming all data has been received...')
        while len(chunk) < data_len:
            chunk = chunk + self.sock.recv(data_len - len(chunk))

        return_msg = chunk.decode()
        logger.debug(f'Return message received and decoded: {return_msg}')
        return return_msg

    def handle_server_response(self, data_type, job_type):
        read_sockets, write_sockets, error_sockets = select.select([self.sock], [], [])

        if read_sockets[0] == self.sock:
            return_msg = self.receive_from_server()
            if job_type == 'save':
                speak(return_msg)

            if 'ERROR: ' not in return_msg:
                if job_type == 'show' or (data_type == 'coordinates' and job_type == 'use'):
                    return return_msg

                elif data_type == 'protocol' and job_type == 'use':
                    operations_string = return_msg.replace("]", "").replace("'", "")
                    logger.debug(f'Received operations from server:  {operations_string}')
                    q = queue.Queue()
                    operations_lst = operations_string.split(', ')
                    while operations_lst:
                        logger.debug(f'Inserting operation into protocol queue: {operations_lst[0]}')
                        q.put(operations_lst.pop(0))
                    return q

                logger.info(return_msg)
            else:
                logger.error(return_msg)
                with self.request_queue.mutex:
                    logger.debug('Clearing request queue')
                    self.request_queue.queue.clear()
                self.noError = False
                speak(return_msg)

    def send_then_handle(self, job_key, data):
        if data is not None:
            logger.debug(f'Sending job key {job_key} to server, then awaiting confirmation...')
            self.sock.send(job_key.encode('UTF-8'))

            ret_key = self.sock.recv(4).decode()
            if ret_key == job_key:
                logger.debug('Confirmed: server received the correct job key. '
                             'Sending data length, followed by the data package')

                self.sock.send(struct.pack('i', len(data)))
                self.sock.send(data.encode('UTF-8'))

                # Now to handle the data that was returned from the server
                if job_key == 'svlc':
                    logger.debug(f'Sent {data} to server to save the COORDINATES on it.')
                    self.handle_server_response('coordinates', 'save')

                elif job_key == 'svpc':
                    logger.debug(f'Sent {data} to server to save the PROTOCOL on it.')
                    self.handle_server_response('protocol', 'save')

                elif job_key == 'shlc':
                    logger.debug(f'Sent the search word {data} to server to get LOCATION ENTRIES from it.')
                    return self.handle_server_response('location', 'show')

                elif job_key == 'shpc':
                    logger.debug(f'Sent the search word {data} to server to get PROTOCOL ENTRIES from it.')
                    return self.handle_server_response('protocol', 'show')

                elif job_key == 'gtlc':
                    logger.debug(f'Sent the location name {data} to the server to get COORDINATES from it')
                    return self.handle_server_response('coordinates', 'use')

                else:  # job key is 'gtpc' (get protocol)
                    logger.debug(f'Sent the protocol name {data} to server to get PROTOCOL OPERATIONS from it.')
                    return self.handle_server_response('protocol', 'use')
            else:
                logger.critical(f'Request key did not return the same: {ret_key}')
                self.noError = False
        else:
            logger.error('data to be sent is None, therefore no sending operation was made.')
            self.noError = False

    def keyboard_type(self):
        logger.debug('Identified "keyboard_type" request')
        try:
            sentence = self.current_request.split("type ", maxsplit=1)[1]
            pyautogui.write(sentence)
            logger.info(f"text written: {sentence}")
            time.sleep(1)
        except IndexError:
            logger.critical('The program did not sort the request correctly. URGENTLY find why.')

    def fast_travel(self):
        logger.debug('Identified "fast travel" request')
        coordinates_entry = mouseControl.mouse_location_get_entry(self.current_request)
        coordinates= self.send_then_handle('gtlc', coordinates_entry)

        mouseControl.mouse_location_travel(coordinates, coordinates_entry)

    def save_location_entry(self):
        logger.debug('Identified "save location entry" request')
        save_data = mouseControl.mouse_location_save_data(self.current_request)
        self.send_then_handle('svlc', save_data)

    def save_rec_protocol(self):
        logger.debug('Identified "save recording as protocol" request')
        if self.pcl_tracker.protocol_recording_switches['protocol_recording']:
            self.pcl_tracker.protocol_recording_switches['protocol_save'] = True
        else:
            logger.warning("No recording has begun yet, therefore ignoring this request.")
            self.noError = False

    def start_rec_protocol(self):
        logger.debug('Identified "start recording protocol" request')
        self.pcl_tracker.protocol_recording_switches['protocol_recording'] = True
        speak('Recording')

    def speak_entries(self):
        logger.debug('Identified "display related entries" request')
        try:
            shared_word = self.current_request.split(' with ')[1]
            if ' protocol' in self.current_request:
                job_key = 'shpc'
            elif ' location' in self.current_request:
                job_key = 'shlc'
            else:
                self.noError = False
                logger.warning('No entry type was specified, ignoring request.')
                return
        except IndexError:
            logger.warning('User omitted search word from request, ignoring request.')
            self.noError = False
            return
        entries = self.send_then_handle(job_key, shared_word)
        speak(entries)

    def execute_protocol(self):
        logger.debug('Identified "execute protocol" request')
        try:
            protocol_entry = self.current_request.split('protocol ')[1]
        except IndexError:
            logger.warning('User omitted protocol entry from request, ignoring request.')
            self.noError = False
            return
        protocol_queue = self.send_then_handle('gtpc', protocol_entry)
        if protocol_queue:
            # re-organizing request queue:
            while not self.request_queue.empty():
                protocol_queue.put(self.request_queue.get())
            while not protocol_queue.empty():
                self.request_queue.put(protocol_queue.get())

    def press_enter(self):
        logger.debug('Identified "press enter" request')
        pyautogui.press('enter')
        logger.info("pressed ENTER on the keyboard.")
        time.sleep(1)

    def back_history_browser(self):
        logger.debug('Identified "go to last page in browser" request')
        pyautogui.hotkey('alt', 'left')
        logger.info("MOVED BACK in browser history.")
        time.sleep(1)

    def forward_history_browser(self):
        logger.debug('Identified "go to next page in browser" request')
        pyautogui.hotkey('alt', 'right')
        logger.info("MOVED FORWARD in browser history.")
        time.sleep(1)

    def click_mouse(self):
        logger.debug('Identified "click the mouse" request')
        if 'double' in self.current_request and 'click' in self.current_request:
            mouse.double_click('left')
            logger.info('double-left clicked')
            time.sleep(1)
        elif 'double' in self.current_request and 'right' in self.current_request:
            mouse.double_click('right')
            logger.info('double-right clicked')
            time.sleep(1)

        elif 'right' in self.current_request:
            mouse.click('right')
            logger.info("right clicked")
            time.sleep(1)
        else:
            mouse.click('left')
            logger.info("left clicked")
            time.sleep(1)

    def scroll_mouse(self):
        logger.debug('Identified "scroll the mouse wheel" request')
        for i in reversed(range(1, 100)):
            if f'{i}' in self.current_request:
                if 'up' in self.current_request:
                    mouse.wheel(5)

                elif 'down' in self.current_request:
                    mouse.wheel(-5)

    def move_mouse_pointer(self):
        logger.debug('Identified "move mouse-pointer" request')
        num = 0
        for i in reversed(range(1, 2000)):
            if f"{i}" in self.current_request and ("down" in self.current_request or "right" in self.current_request):
                num = i
                break
            elif f"{i}" in self.current_request and ("up" in self.current_request or "off" in self.current_request or "left" in self.current_request):
                num = -i
                break

        if "up" in self.current_request or "off" in self.current_request or "down" in self.current_request:
            mouse.move(0, num, absolute=False, duration=0.1)
            time.sleep(0.1)
            logger.info(f"Moved {num} units on the y axis.")

        elif "right" in self.current_request or "left" in self.current_request:
            mouse.move(num, 0, absolute=False, duration=0.1)
            time.sleep(0.1)
            logger.info(f"Moved {num} units on the x axis.")

    def press_left_arrow(self):
        logger.debug('Identified "press left arrow" request')
        pyautogui.press('left')
        logger.info('pressed LEFT ARROW on the keyboard')
        time.sleep(0.1)

    def press_right_arrow(self):
        logger.debug('Identified "press right arrow" request')
        pyautogui.press('right')
        logger.info('pressed RIGHT ARROW on the keyboard')
        time.sleep(0.1)

    def press_up_arrow(self):
        logger.debug('Identified "press up arrow" request')
        pyautogui.press('up')
        logger.info('pressed UP ARROW on the keyboard')
        time.sleep(0.1)

    def shutdown_program(self):
        logger.debug('Identified "shutdown" request')
        logger.info("exiting program.\r\n\r\n")
        self.program_switch[0] = False

    def press_down_arrow(self):
        logger.debug('Identified "press down arrow" request')
        pyautogui.press('down')
        logger.info('pressed DOWN ARROW on the keyboard')
        time.sleep(0.1)

    def press_backspace(self):
        logger.debug('Identified "press backspace" request')
        pyautogui.press('backspace')
        logger.info('pressed BACKSPACE on the keyboard. ')
        time.sleep(0.1)

    def open_new_tab(self):
        logger.debug('Identified "open new tab" request')
        pyautogui.hotkey('ctrl', 't')
        logger.info("OPENED NEW TAB in browser.")
        time.sleep(1)

    def open_new_window(self):
        logger.debug('Identified "open new window" request')
        pyautogui.hotkey('ctrl', 'n')
        logger.info("OPENED NEW browser WINDOW.")
        time.sleep(1)

    def next_tab_browser(self):
        logger.debug('Identified "select next tab in browser" request')
        pyautogui.hotkey('ctrl', 'tab')
        logger.info("Cycled to NEXT TAB.")
        time.sleep(1)

    def press_tab(self):
        logger.debug('Identified "press tab" request')
        pyautogui.press('tab')
        logger.info('pressed TAB on the keyboard.')
        time.sleep(0.1)

    def close_window(self):
        logger.debug('Identified "close window" request')
        pyautogui.hotkey('alt', 'f4')
        logger.info("CLOSED APPLICATION.")
        time.sleep(1)

    def close_tab(self):
        logger.debug('Identified "close tab" request')
        pyautogui.hotkey('ctrl', 'f4')
        logger.info("CLOSED TAB in browser.")
        time.sleep(1)

    def add_bookmark(self):
        logger.debug('Identified "add page to bookmarks" request')
        pyautogui.hotkey('ctrl', 'd')
        logger.info("BOOKMARKED page in browser.")
        time.sleep(1)

    def find_in_browser(self):
        logger.debug('Identified "open text finder in browser" request')
        pyautogui.hotkey('ctrl', 'g')
        logger.info("opened and selected TEXT FINDER prompt")
        time.sleep(0.5)

    def open_history_browser(self):
        logger.debug('Identified "open history manager in browser" request')
        pyautogui.hotkey('ctrl', 'h')
        logger.info("opened HISTORY tab in browser.")
        time.sleep(1)

    def refresh_browser(self):
        logger.debug('Identified "refresh browser page" request')
        pyautogui.press('browserrefresh')
        logger.info("refreshed page in browser.")
        time.sleep(2)

    def search_bar_browser(self):
        logger.debug('Identified "select search bar in browser" request')
        pyautogui.hotkey('alt', 'd')
        pyautogui.press('browsersearch')
        logger.info("selected search bar.")
        time.sleep(1)

    def play_pause_video(self):
        logger.debug('Identified "play or pause video" request')
        pyautogui.press('playpause')
        logger.info("PLAYED or PAUSED a video.")
        time.sleep(1)

    def time_sleep(self):
        time.sleep(3)

    def junk(self):
        logger.debug('Identified "junk" request')
        self.noError = False

    keyword_sorter = {
        keyboard_type: {'type', 'tyke', 'tight'},
        junk: {'misunderstanding', 'sorry', 'mistake', 'never', 'mind', 'nevermind'},
        fast_travel: {'travel', 'trouble'},
        save_location_entry: [{'location', 'coordinates'},
                              {'save', 'safecoin', 'safecon', 'safe', 'safecard', 'safeguard', 'steve'}],
        save_rec_protocol: [{'protocol'}, {'save', 'safe', 'stop'}],
        start_rec_protocol: [{'protocol'}, {'recording', 'record'}],
        speak_entries: [{'protocol', 'protocols', 'location', 'locations'}, {'show', 'display', 'present', 'say', 'safety', 'what'}],
        execute_protocol: {'protocol'},
        time_sleep: {'wait', 'weight'},
        press_enter: {'enter'},
        close_window: [{'close'}, {'window', 'application'}],
        close_tab: [{'close', 'clothes'}, {'tab'}],
        open_new_tab: [{'open'}, {'tab'}],
        open_new_window: [{'open'}, {'window'}],
        add_bookmark: {'bookmark'},
        find_in_browser: {'find'},
        open_history_browser: {'history'},
        refresh_browser: {'refresh'},
        search_bar_browser: [{'select'}, {'search'}],
        next_tab_browser: [{'select', 'switch'}, {'next', 'tab'}],
        press_tab: {'tab'},
        play_pause_video: {"play", "pause", "paul's"},
        back_history_browser: [{'back', 'return', 'last'}, {'page'}],
        forward_history_browser: [{'forward', 'next'}, {'page'}],
        click_mouse: {'click', 'clicks', 'clicking', 'quik', 'flick', 'slick', 'double-click'},
        scroll_mouse: {'scroll'},
        move_mouse_pointer: {'move', 'movie', 'moves'},
        press_left_arrow: {'left'},
        press_right_arrow: {'right'},
        press_up_arrow: {'up', 'off'},
        shutdown_program: {'exit', 'bye', 'goodbye', 'shutdown', 'shut'},
        press_down_arrow: {'down'},
        press_backspace: {'delete'}
    }


# -------------------------------------------------------------- #


def speak(sentence):
    speaker = VOp.Speaker(0, 200)
    speaker.speak(sentence)
    del speaker


def setup_logging():
    fmt = '%(asctime)s | %(threadName)s - %(levelname)s - %(filename)s - %(lineno)s - func=%(funcName)s : "%(message)s"'
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters':
            {
                'standard':
                    {
                        'format': fmt
                    }
            },
        'handlers':
            {
                'default':
                    {
                        'class': 'logging.StreamHandler',
                        'formatter': 'standard',
                        'level': 'DEBUG',
                        'stream': 'ext://sys.stdout'
                    },
                'toSocket':
                    {
                        'class': 'logging.handlers.SocketHandler',
                        'level': 'DEBUG',
                        'host': SERVER_IP,
                        'port': f'{logging.handlers.DEFAULT_TCP_LOGGING_PORT}'
                    },
            },
        'loggers':
            {
                'logger':
                    {
                        'handlers': ['default', 'toSocket'],
                        'level': 'DEBUG',
                        'propagate': False
                    }
            }
    }

    logging.config.dictConfig(logging_config)


def main_setup():
    # logging set-up.
    setup_logging()
    logging.getLogger("comtypes").setLevel(logging.INFO)

    speak("Thank you for waking me up, operator! I am Dayjay.")

    # Socket set-up.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, PORT))

    # Finally, setting up the red_dot object, the request_queue and the mutable boolean values inside the return statement.
    return s, ProtocolController(), DeijeyGraphics.recording_dot(), queue.Queue(), [True]


def main():
    my_socket, pcl_tracker, red_dot, request_queue, on_off_switch = main_setup()
    """
    Sequence words: separate requests in sentence
    Cutting words: cancel requests in sentence
    """
    sequence_words = [" and then ", " afterwards ", " finally ", " while ", " meanwhile ", " and ", " than "]
    cutting_words = ['never', 'mind', 'nevermind']
    while on_off_switch[0]:
        print("\n\n\n\n\n ---------------------------------------------------------------")
        print(f"Number of active threads: {threading.active_count()}")
        text = str(VOp.from_mic(red_dot).lower())

        if text == "":
            continue

        if KEYWORD in text:  # Listen for the keyword
            timer_start = time.perf_counter()

            text = text.replace(f" {KEYWORD} ", " ").replace(f" {KEYWORD}", "").replace(f"{KEYWORD} ", "")
            for word in sequence_words:
                text = text.replace(word, " then ")
            for word in cutting_words:
                text = text.replace(word, ' nevermind ')

            """
            Cut requests that have been canceled mid-speech, then
            Split sentence into requests through usage of connection words.
            """
            while ' nevermind ' in text:
                text = text.split(' nevermind ', maxsplit=1)[1]
            if text == '':
                logger.debug('Requests were all canceled. Listening...')
                continue

            if " then " in text:
                text = text.split(" then ")
                logger.debug(f"sentence split into requests: {text}")

            if isinstance(text, list):  # If the sentence was changed by simplification, it's a sequenced request.
                for nested_request in text:
                    logger.debug(f"queuing request for request_handler function: {nested_request}")
                    request_queue.put(nested_request)

                request_thread = RequestHandlerThread(request_queue, my_socket, timer_start, pcl_tracker, on_off_switch)
                request_thread.start()
            else:
                logger.debug(f"queuing request for request_handler function: {text}")
                request_queue.put(text)

                request_thread = RequestHandlerThread(request_queue, my_socket, timer_start, pcl_tracker, on_off_switch)
                request_thread.start()

            request_thread.join()
    my_socket.shutdown(socket.SHUT_RDWR)
    my_socket.close()


if __name__ == '__main__':
    logger = logging.getLogger('logger')
    main()
