import unittest
from src.austin_heller_repo.threading import MemorySequentialQueue, MemorySequentialQueueReader, MemorySequentialQueueWriter, start_thread, Semaphore, SingletonMemorySequentialQueue, SingletonMemorySequentialQueueFactory, SingletonMemorySequentialQueueReader, SingletonMemorySequentialQueueWriter


def get_default_singleton_memory_sequential_queue_factory() -> SingletonMemorySequentialQueueFactory:
	return SingletonMemorySequentialQueueFactory(
		reader_failed_read_delay_seconds=0
	)


class SingletonMemorySequentialQueueTest(unittest.TestCase):

	def test_initialize(self):

		sequential_queue_factory = get_default_singleton_memory_sequential_queue_factory()

		self.assertIsNotNone(sequential_queue_factory)

		sequential_queue = sequential_queue_factory.get_sequential_queue()

		self.assertIsNotNone(sequential_queue)

	def test_queue_and_dequeue(self):

		sequential_queue_factory = get_default_singleton_memory_sequential_queue_factory()

		sequential_queue = sequential_queue_factory.get_sequential_queue()

		sequential_queue_writer = sequential_queue.get_writer().get_result()  # type: SingletonMemorySequentialQueueWriter

		sequential_queue_reader = sequential_queue.get_reader().get_result()  # type: SingletonMemorySequentialQueueReader

		expected_message_bytes = b"test"

		sequential_queue_writer.write_bytes(
			message_bytes=expected_message_bytes
		).get_result()

		actual_message_bytes = sequential_queue_reader.read_bytes().get_result()  # type: bytes

		self.assertEqual(expected_message_bytes, actual_message_bytes)

		sequential_queue.dispose()
