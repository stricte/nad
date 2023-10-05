import time
import threading


def debounce(wait):
    """
    Decorator factory for creating a debounce decorator with a custom wait time.
    """

    def decorator(func):
        def debounced(*args, **kwargs):
            def call_it():
                func(*args, **kwargs)

            if hasattr(debounced, "_timer"):
                # If there's an existing timer, cancel it
                debounced._timer.cancel()

            # Create a new timer with the specified wait time
            debounced._timer = threading.Timer(wait, call_it)
            debounced._timer.start()

        return debounced

    return decorator
