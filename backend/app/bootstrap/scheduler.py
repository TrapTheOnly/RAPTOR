import atexit
import threading
from typing import Callable

update_stop_event = threading.Event()


def stop_periodic_update() -> None:
    update_stop_event.set()


def periodic_update(interval: int, update_function: Callable[[], None]) -> None:
    """
    Runs `update_function` every `interval` seconds in a separate thread.
    """

    def wrapper() -> None:
        if update_stop_event.is_set():
            return
        update_function()
        timer = threading.Timer(interval, wrapper)
        timer.daemon = True
        timer.start()

    timer = threading.Timer(interval, wrapper)
    timer.daemon = True
    timer.start()


atexit.register(stop_periodic_update)
