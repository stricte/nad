from threading import Event, Thread


class PostponedCommandScheduler:
    def __init__(self, processor, logger, config) -> None:
        self.processor = processor
        self.logger = logger
        self.config = config
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is not None:
            return

        self.stop_event.clear()
        self.thread = Thread(target=self.__run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread is None:
            return

        self.stop_event.set()
        self.thread.join(timeout=1)
        self.thread = None

    def run_once(self):
        try:
            self.processor.process_postponed()
        except Exception as exc:
            self.logger.error(f"Postponed command scheduler error: {exc}")

    def __run(self):
        while not self.stop_event.is_set():
            self.run_once()
            self.stop_event.wait(self.config.postponed_processor_interval_seconds)
