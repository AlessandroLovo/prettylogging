import logging
from datetime import datetime
from functools import wraps
import time
import sys
import os
import traceback
from pathlib import Path

if __name__ == '__main__':
    module_logger = logging.getLogger()
    module_logger.handlers = [logging.StreamHandler(sys.stdout)]
else:
    module_logger = logging.getLogger(__name__)
module_logger.level = logging.INFO

MAX_FILENAME_LENGTH = 128
default_formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
indentation_sep = '\t' # spacing amount at each indentation


### time ###
def now():
    '''
    Returns the current time as string formatted as year-month-day hour:minute:second
    '''
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def pretty_time(t:float) -> str:
    '''
    Takes a time in seconds and returns it in a string with the format <hours> h <minutes> min <seconds> s

    Examples
    --------
    >>> pretty_time(124)
    '2 min 4.0 s'
    >>> pretty_time(3601.4)
    '1 h 1.4 s'
    '''
    h = t//3600
    t = t - h*3600
    m = t//60
    s = t - m*60
    pt = ''
    if h > 0:
        pt += f'{h:.0f} h '
    if m > 0:
        pt += f'{m:.0f} min '
    pt += f'{s:.1f} s'
    return pt

###### function decorators for logging ###

## indenting ####
def get_logger(logger):
    if logger is None:
        logger = logging.getLogger()
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    return logger

def indent_write(write):
    '''
    decorator for a function that writes to a stream, e.g. sys.stdout or a file. Indents the message.

    Examples
    --------
    >>> def test():
    ...     print('before')
    ...     old_write = sys.stdout.write
    ...     sys.stdout.write = indent_write(sys.stdout.write)
    ...     print('Hello!')
    ...     sys.stdout.write = old_write
    ...     print('after')

    Will give output
    before
        Hello!
    after
    '''
    @wraps(write)
    def wrapper(message):
        message = (indentation_sep+f'\n{indentation_sep}'.join(message[:-1].split('\n')) + message[-1])
        return write(message)
    return wrapper

def indent(*streams):
    '''
    Returns a decorator that indents the output produced by the decorated function on the streams provided

    Examples
    --------
    >>> @indent(sys.stdout)
    ... def show(a=0):
    ...     print(f'{a = }')
    >>> def test(a=0):
    ...     print('before')
    ...     show(a)
    ...     print('after')

    When running `test(24)` you will get
    before
        a = 24
    after

    Indentation can be chained

    >>> @indent(sys.stdout)
    ... def test_innner(a=0):
    ...     print('before inner')
    ...     show(a)
    ...     print('after inner')
    >>> def test_outer(a=0):
    ...     print('before outer')
    ...     test_inner(a)
    ...     print('after outer')

    test_outer(24) will give
    before outer
        before inner
            a = 24
        after inner
    after outer

    You can also indent a handler `h` of the logging module by creating a decorator @indent(h.stream)
    '''
    def wrapper_outer(func):
        @wraps(func)
        def wrapper_inner(*args, **kwargs):
            # save old write and emit functions
            old_write = [stream.write if hasattr(stream, 'write') else None for stream in streams]
            # indent write and emit functions
            for i,stream in enumerate(streams):
                if old_write[i] is not None:
                    stream.write = indent_write(stream.write)
            try:
                r = func(*args, **kwargs)
            finally:
                # restore original functions
                for i,stream in enumerate(streams):
                    if old_write[i] is not None:
                        stream.write = old_write[i]
            return r
        return wrapper_inner
    return wrapper_outer

def indent_logger(logger=None):
    '''
    Indents all handlers of a given logger when the decorated function is running

    Parameters
    ----------
    logger : logging.loggers.Logger, optional
        logger, if None the root logger is used. The default is None
    '''
    logger = get_logger(logger)
    def wrapper_outer(func):
        @wraps(func)
        def wrapper_inner(*args, **kwargs):
            streams = []
            # get the handlers of the logger and its parents
            c = logger
            while c:
                # # avoid indenting the same stream more than once
                # # in case both a logger and one of its parent log to the same stream, which would be silly anyways
                # _streams = [h.stream for h in c.handlers if hasattr(h, 'stream')]
                # for s in _streams:
                #     if s not in streams:
                #         streams.append(s)

                # assuming the loggers are not silly and so no stream is repeated
                streams += [h.stream for h in c.handlers if hasattr(h, 'stream')]
                if not c.propagate:
                    c = None    #break out
                else:
                    c = c.parent

            # save old write functions
            old_write = [stream.write if hasattr(stream, 'write') else None for stream in streams]
            # indent write functions
            for i,stream in enumerate(streams):
                if old_write[i] is not None:
                    stream.write = indent_write(stream.write)
            try:
                r = func(*args, **kwargs)
            finally:
                # restore original functions
                for i,stream in enumerate(streams):
                    if old_write[i] is not None:
                        stream.write = old_write[i]
            return r
        return wrapper_inner
    return wrapper_outer

def indent_stdout(func):
    '''
    Indents the stdout output produced by a function
    '''
    return indent(sys.stdout)(func)

## execution time
def exec_time(logger=None):
    '''
    Prints the execution time of a function

    Examples
    --------
    >>> logger.handlers = [logging.StreamHandler(sys.stdout)]
    >>> @exec_time(logger)
    ... def test(a):
    ...     time.sleep(1)
    ...     logger.info(a)
    >>> test('Hi')
    test:
    Hi
    test: completed in 1.0 s
    '''
    logger = get_logger(logger)
    def wrapper_outer(func):
        @wraps(func)
        def wrapper_inner(*args, **kwargs):
            start_time = time.time()
            logger.info(f'{func.__name__}:')
            r = func(*args, **kwargs)
            logger.info(f'{func.__name__}: completed in {pretty_time(time.time() - start_time)}')
            return r
        return wrapper_inner
    return wrapper_outer

#### TELEGRAM LOGGER ####

def new_telegram_handler(chat_ID=None, token=None, level=logging.WARNING, formatter=default_formatter, **kwargs):
    '''
    Creates a telegram handler object.

    To log to telegram you need to use a telegram Bot. You can create one by typing the command /newbot in the chat with the BotFather. When you finalize your bot, the BotFather will give you the authorization token.
    To be able to receive messages from the bot you will first need to start a chat with it using the command /start

    Parameters
    ----------
    chat_ID : int or str, optional
        chat ID of the telegram user or group to whom send the logs. If str it is a path to a file where it is stored.
        To find your chat ID go to telegram and search for 'userinfobot' and type '/start'. The bot will provide you with your chat ID.
        You can do the same with a telegram group, and, in this case, you will need to invite 'MyBot' to the group.
        The default is None.
    token: str
        token for the telegram bot or path to a text file where the first line is the token
    level : int or logging.(NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL), optional
        The default is logging.WARNING.
    formatter : logging.Formatter, str or None, optional
        The formatter used to log the messages. The default is default_formatter.
        If string it can be for example '%(levelname)s: %(message)s'
    **kwargs :
        additional arguments for telegram_handler.handlers.TelegramHandler

    Returns
    -------
    th: telegram_handler.handlers.TelegramHandler
        handler that logs to telegram
    '''
    try:
        import telegram_handler # NOTE: to install this package run pip install python-telegram-handler
    except ImportError:
        module_logger.error('To be able to log to telegram, you need the package telegram_handler. You can install it with `pip install python-telegram-handler`')
        return
    if chat_ID is None or token is None:
        return

    try:
        chat_ID = int(chat_ID)
    except: # `chat_ID is either string or path`
        if isinstance(chat_ID, str) and chat_ID.startswith('~'):
            chat_ID = f"{os.environ['HOME']}{chat_ID[1:]}"
        with open(chat_ID, 'r') as chat_ID_file:
            chat_ID = int(chat_ID_file.readline().rstrip('\n'))
    if not chat_ID: # chat ID 0 disables the logger
        return

    try:
        if token.startswith('~'):
            token = f"{os.environ['HOME']}{token[1:]}"
        with open(token, 'r') as token_file:
            token = token_file.readline().rstrip('\n')
    except FileNotFoundError:
        pass # we assume that `token` is the actual token, not the path to it

    th = telegram_handler.handlers.TelegramHandler(token=token, chat_id=chat_ID, **kwargs)
    if isinstance(formatter, str):
        if formatter == 'default':
            formatter = default_formatter
        else:
            formatter = logging.Formatter(formatter)
    if formatter is not None:
        th.setFormatter(formatter)
    th.setLevel(level)
    return th




#### LOGGERS AS CONTEXT MANAGERS ####

class CMLogger():
    def __init__(self, logger: logging.Logger, level=logging.INFO):
        self.logger = logger
        self.level = int(level)

        self.handler = None

    def create_new_handler(self):
        raise NotImplementedError('This is the base class you fool!')

    def __enter__(self):
        try:
            self.create_new_handler()
        except:
            self.logger.error(f'Failed to create new handler for {self.__class__.__name__} due to \n\n{traceback.format_exc()}')

        if self.handler is not None:
            self.logger.handlers.append(self.handler)
            self.logger.debug(f'Added {self.__class__.__name__}')

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.handler is not None:
            if exc_type is not None:
                self.logger.error(traceback.format_exc())
            self.logger.handlers.remove(self.handler)
            self.logger.debug(f'Removed {self.__class__.__name__}')


class TelegramLogger(CMLogger):
    def __init__(self, logger: logging.Logger, chat_ID: int=None, token: str=None, level=logging.INFO, **kwargs):
        '''
        Telegram logger to be used with a `with` statement. If an unhandled exception is raised in the with block, the traceback will also be logged to telegram with level logging.ERROR

        To log to telegram you need to use a telegram Bot. You can create one by typing the command /newbot in the chat with the BotFather. When you finalize your bot, the BotFather will give you the authorization token.
        To be able to receive messages from the bot you will first need to start a chat with it using the command /start

        Parameters
        ----------
        logger : logging.Logger
            logger to which to add a telegram handler
            chat_ID : int or str, optional
            chat ID of the telegram user or group to whom send the logs. If str it is a path to a file where it is stored.
            To find your chat ID go to telegram and search for 'userinfobot' and type '/start'. The bot will provide you with your chat ID.
            You can do the same with a telegram group, and, in this case, you will need to invite 'MyBot' to the group.
            The default is None.
        token: str
            token for the telegram bot or path to a text file where the first line is the token
        level : int, optional
            logging level, by default logging.INFO

        Additional arguments will be passed to `new_telegram_handler`

        Examples
        --------
        >>> with TelegramLogger(logging.getLogger(), '~/telegram_chat_ID.txt', '~/telegram_bot_token.txt', level=logging.WARNING):
        ...     logging.error('Oh no an error occurred')

        You can also use a specific logger instead of the root one
        >>> logger = logging.getLogger('myLogger')
        >>> with TelegramLogger(logger, '~/telegram_chat_ID.txt', '~/telegram_bot_token.txt', level=logging.WARNING):
        ...     logger.error('Oh no an error occurred')
        '''
        super().__init__(logger=logger, level=level)
        self.chat_ID = chat_ID
        self.token = token
        self.kwargs = kwargs

    def create_new_handler(self):
        self.handler = new_telegram_handler(self.chat_ID, self.token, level=self.level, **self.kwargs)

class FileLogger(CMLogger):
    def __init__(self, logger: logging.Logger, filename: str, level=logging.INFO, **kwargs):
        '''
        Logger to file to be used with the `with` statement. If an unhandled exception is raised in the with block, the traceback will also be logged to the file with level logging.ERROR

        Parameters
        ----------
        logger : logging.Logger
            logger to which to add a file handler
        filename : str|Path
            path to the file to log to. If it is inside a directory that doesn't exist, the tree of directories is created
        level : int, optional
            logging level, by default logging.INFO

        Additional arguments are passed to logging.FileHandler constructor. For example, the mode with which to open the file (default 'a')

        Examples
        --------
        >>> with FileLogger(logging.getLogger(), 'log.log', level=logging.WARNING):
        ...     logging.error('Oh no an error occurred')

        You can also use a specific logger instead of the root one
        >>> logger = logging.getLogger('myLogger')
        >>> with FileLogger(logger, 'log.log', level=logging.WARNING):
        ...     logger.error('Oh no an error occurred')
        '''
        super().__init__(logger=logger, level=level)
        self.filename = Path(filename)
        self.kwargs = kwargs

    def create_new_handler(self):
        parent_dir = self.filename.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        self.handler = logging.FileHandler(filename=self.filename, **self.kwargs)


