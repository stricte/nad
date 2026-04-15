import unittest
from types import SimpleNamespace

from postponed_command_scheduler import PostponedCommandScheduler


class FakeProcessor:
    def __init__(self) -> None:
        self.calls = 0

    def process_postponed(self):
        self.calls += 1


class FailingProcessor:
    def process_postponed(self):
        raise RuntimeError("boom")


class FakeLogger:
    def __init__(self) -> None:
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class PostponedCommandSchedulerTests(unittest.TestCase):
    def test_run_once_processes_postponed_commands(self):
        processor = FakeProcessor()
        scheduler = PostponedCommandScheduler(
            processor,
            FakeLogger(),
            SimpleNamespace(postponed_processor_interval_seconds=0.1),
        )

        scheduler.run_once()

        self.assertEqual(processor.calls, 1)

    def test_run_once_logs_processor_errors(self):
        logger = FakeLogger()
        scheduler = PostponedCommandScheduler(
            FailingProcessor(),
            logger,
            SimpleNamespace(postponed_processor_interval_seconds=0.1),
        )

        scheduler.run_once()

        self.assertEqual(
            logger.errors,
            ["Postponed command scheduler error: boom"],
        )

    def test_start_and_stop_manage_thread_lifecycle(self):
        scheduler = PostponedCommandScheduler(
            FakeProcessor(),
            FakeLogger(),
            SimpleNamespace(postponed_processor_interval_seconds=1),
        )

        scheduler.start()
        self.assertIsNotNone(scheduler.thread)

        scheduler.stop()
        self.assertIsNone(scheduler.thread)


if __name__ == "__main__":
    unittest.main()
