import _pickle as pickle
import logging
import logging.handlers
import os
import socket
import socketserver
import struct
import threading
from logging.config import dictConfig

import select

LOG_FORMAT = '%(asctime)s | %(threadName)s - %(levelname)s - %(filename)s / %(name)s - %(lineno)s - func=%(funcName)s : "%(message)s"'
IP, PORT = '0.0.0.0', 4001


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """
    Handler for a streaming logging request.

    This basically logs the record using whatever logging policy is
    configured locally.
    """

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            try:
                chunk = self.connection.recv(4)
                if len(chunk) < 4:
                    break
                slen = struct.unpack('>L', chunk)[0]
                chunk = self.connection.recv(slen)
                while len(chunk) < slen:
                    chunk = chunk + self.connection.recv(slen - len(chunk))
                obj = self.unPickle(chunk)
                record = logging.makeLogRecord(obj)
                self.handleLogRecord(record)
            except ConnectionResetError:
                main_logger.error('Client crashed or forcibly closed')
                break
            except ConnectionAbortedError:
                main_logger.exception('ConnectionAboredError: ', exc_info=True)
                break

    @staticmethod
    def unPickle(data):
        return pickle.loads(data)

    def handleLogRecord(self, record):
        # if a name is specified, we use the named logger rather than the one
        # implied by the record.
        if self.server.logname is not None:
            name = self.server.logname
        else:
            name = record.name
        logger = logging.getLogger(name)
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering.
        logger.handle(record)


class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    """
    Simple TCP socket-based logging receiver suitable for testing.
    """

    allow_reuse_address = True

    def __init__(self,
                 host=socket.gethostbyname(socket.gethostname()),
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                 handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()], [], [], self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort


class ClientHandlerThread(threading.Thread):
    def __init__(self, sock, client_address):
        super().__init__()
        self.sock = sock
        self.client_address = client_address
        self.current_job_data = None
        self.job_key = None

    def run(self):
        """
            Constantly check socket status using 'select'.
            When a request comes in, identify it and
            Call the appropriate service with the appropriate orders.

            Finally, send the data back (with ERROR label in case of an error)
        """
        while True:
            self.current_job_data, self.job_key = None, None
            main_logger.debug('Waiting for job key to arrive in socket...')
            read_socket, write_sockets, error_sockets = select.select([self.sock], [], [])
            if read_socket[0] == self.sock:
                try:
                    self.job_key = self.sock.recv(4).decode()
                except ConnectionResetError:
                    main_logger.error(f'Client {self.client_address[0]} crashed or forcibly closed')
                    break
                if self.job_key == "":
                    main_logger.info(f'Connection was lawfully terminated with {self.client_address[0]}')
                    break
                main_logger.debug(f'Job key arrived in socket: {self.job_key}')

                self.sock.send(f'{self.job_key}'.encode('UTF-8'))
                main_logger.debug('Sent the key back to client for confirmation')
                self.current_job_data = self.receive_from_client()
                main_logger.debug(f'Received job data: {self.current_job_data}. Initiating job_handler')
                if self.job_key == 'svlc':
                    return_msg = self.save_to_file('coordinates')

                elif self.job_key == 'gtlc':
                    return_msg = self.from_file('coordinates')

                elif self.job_key == 'shlc':
                    return_msg = self.from_file('coordinates')

                elif self.job_key == 'svpc':
                    return_msg = self.save_to_file('protocols')

                elif self.job_key == 'gtpc':
                    return_msg = self.from_file('protocols')

                elif self.job_key == 'shpc':
                    return_msg = self.from_file('protocols')

                else:
                    main_logger.error(f'Server does not provide service to self.job_key = {self.job_key}')
                    return_msg = f'Server does not provide service to self.job_key = {self.job_key}'

                main_logger.debug(return_msg)
                main_logger.debug(f'About to send message to socket: {return_msg}')
                self.sock.send(struct.pack('i', len(return_msg)))
                self.sock.send(return_msg.encode('UTF-8'))

    def receive_from_client(self):
        packed_length = self.sock.recv(4)
        main_logger.debug('Received incoming data length, waiting for job data to arrive.')
        try:
            data_len = struct.unpack('i', packed_length)[0]
        except struct.error:
            return None
        main_logger.debug('About to receive data from client:')
        chunk = self.sock.recv(data_len)
        while len(chunk) < data_len:
            main_logger.debug('Not all data has been received. Entered receiving loop...')
            chunk = chunk + self.sock.recv(data_len - len(chunk))

        job_data = chunk.decode()
        main_logger.debug('Job data received and decoded!')
        return job_data

    def save_to_file(self, content_type):
        if content_type == 'coordinates':
            separator = '@'
        else:  # content type is protocols
            separator = '['
        entry, content = self.current_job_data.split(separator)
        main_logger.debug(f'Saving to {content_type} file: {entry} - {content}')

        if content_type == 'protocols' and entry == 'junk':
            main_logger.info('Received junk keyword, ignoring request...')
            return 'Received junk keyword, server ignored the data as requested'

        try:
            with open(fr"C:/DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt",
                      "r+") as f:  # Update/create a new entry?
                for line in f.read().splitlines():
                    split_line = line.split(separator)

                    if entry == split_line[0]:  # If true, update the entry.
                        f.seek(0)
                        current_file = f.read()
                        past_content = split_line[1]
                        main_logger.debug(f"Past entry content: {past_content}")
                        replaced_data = current_file.replace(past_content, f"{content}")
                        f.seek(0)
                        f.write(replaced_data)
                        main_logger.info(f"Updated {self.client_address[0]} {content_type} file.")
                        return f'Successfully updated {content_type} entry: {entry}'

            with open(fr"C:\DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt", "a+") as f:  # Create new entry
                f.write(f'\r\n{self.current_job_data}')
                main_logger.info(f"Added {entry} to {self.client_address[0]} {content_type} file")
                return f'Successfully added new entry: {entry}'

        except FileNotFoundError:
            open(rf"C:/DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt",
                 "x").close()  # Create new file, re-call function
            main_logger.warning(f"Created new file to save {content_type} for {self.client_address[0]}.")
            return self.save_to_file(content_type)

        except PermissionError:
            main_logger.exception(
                f"Permission error has occurred in creating/accessing the {self.client_address[0]} {content_type} file. "
                f"Seeking permission", exc_info=True)
            os.chmod(fr"C:/DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt",
                     755)  # Give permission, re-call function
            main_logger.warning("Permission 'os.chmod(755)' given.")
            return self.save_to_file(content_type)

        except IndexError:
            main_logger.exception("Sabotage in the text file data could have caused the exception", exc_info=True)
            return f'ERROR: IndexError occurred while trying to tamper with the {content_type} file. Server received an exception log.'

    def from_file(self, content_type):
        if content_type == 'coordinates':
            separator = '@'
        # else -> content_type is 'protocols':
        else:
            separator = '['

        try:
            with open(fr"C:/DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt", "r") as f:

                if 'sh' in self.job_key:
                    return_value = ''
                    for line in f.read().splitlines():
                        split_line = line.split(separator)
                        if self.current_job_data in split_line[0]:
                            return_value = return_value + split_line[0] + '\r\n'
                            main_logger.debug(f'return_value = {return_value}')
                    return return_value

                else:
                    for line in f.read().splitlines():
                        split_line = line.split(separator)
                        if self.current_job_data == split_line[0]:
                            return_value = split_line[1]
                            return return_value

                    main_logger.error(f"{self.current_job_data} entry not found")
                    return f'ERROR: Entry not found in server files: {self.current_job_data}'

        except FileNotFoundError:
            open(f"C:/DeiJay-Server Data/{self.client_address[0]}/{content_type}.txt",
                 "x").close()  # Create the file, then log the error
            main_logger.error(f"no {content_type} saved yet. ")
            return f'ERROR: No {content_type} were saved yet, the file is empty.'

        except IndexError:
            main_logger.exception("Sabotage in the text file data could have caused the exception", exc_info=True)
            return f'ERROR: IndexError occurred while trying to tamper with the {content_type} file. Server received an exception log.'


class LoggingHandlerThread(threading.Thread):
    def __init__(self, client_address):
        super().__init__()
        self.client_address = client_address

    def run(self):
        setup_socket_logging(rf'C:/DeiJay-Server Data/{self.client_address[0]}/logs', self.client_address)

        tcp_log_server = LogRecordSocketReceiver()
        tcp_log_server.logname = f'{self.client_address}'
        print('About to start TCP logging server...')
        tcp_log_server.serve_until_stopped()


def setup_socket_logging(log_dir, client_address, fmt=LOG_FORMAT):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

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
            'toDebugFile':
            {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'level': 'DEBUG',
                'maxBytes': 1000000,
                'backupCount': 3,
                'filename': f'{log_dir}/debug.log'
            },
            'toErrorFile':
            {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'level': 'WARNING',
                'maxBytes': 100000,
                'backupCount': 7,
                'filename': f'{log_dir}/error.log'
            },
        },
        'loggers':
        {
            f'{client_address}':
            {
                'handlers': ['default', 'toErrorFile', 'toDebugFile'],
                'level': 'DEBUG',
                'propagate': False
            }
        }
    }

    logging.config.dictConfig(logging_config)


def setup_server_logging(log_dir, fmt=LOG_FORMAT):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

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
                    'stream': 'ext://sys.stderr'
            },
            'toDebugFile':
            {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'level': 'DEBUG',
                'maxBytes': 1000000000,
                'backupCount': 7,
                'filename': f'{log_dir}/debug.log'
            },
            'toErrorFile':
            {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'level': 'WARNING',
                'maxBytes': 1000000000,
                'backupCount': 7,
                'filename': f'{log_dir}/error.log'
            },
        },
        'loggers':
        {
            'serverLogger':
            {
                'handlers': ['default', 'toErrorFile', 'toDebugFile'],
                'level': 'DEBUG',
                'propagate': False
            }
        }
    }

    logging.config.dictConfig(logging_config)


def main():
    if not os.path.exists('C:/DeiJay-Server Data'):
        os.mkdir('C:/DeiJay-Server Data')

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((socket.gethostname(), PORT))
        main_logger.debug(f"server bound and listening for clients at {PORT}")
        server_socket.listen(5)

        while True:
            client_socket, address = server_socket.accept()
            main_logger.info(f'Accepted connection from {address[0]}:{address[1]}')

            logging_handler = LoggingHandlerThread(address)
            client_handler = ClientHandlerThread(client_socket, address)
            main_logger.debug('Created threads for client logging and request handling.')

            client_handler.start()
            logging_handler.start()

    except ConnectionResetError:
        main_logger.error('Client crashed or forcibly closed')


if __name__ == '__main__':
    setup_server_logging('C:/DeiJay-Server Data/server logs')
    main_logger = logging.getLogger('serverLogger')
    main()
