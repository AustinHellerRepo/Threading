import unittest
from src.austin_heller_repo.threading import MemorySequentialQueue, MemorySequentialQueueReader, MemorySequentialQueueWriter, start_thread, Semaphore, SingletonMemorySequentialQueue, SingletonMemorySequentialQueueFactory, SingletonMemorySequentialQueueReader, SingletonMemorySequentialQueueWriter, ReadOnlyAsyncHandle, AsyncHandle
from typing import List, Tuple, Dict


def get_default_singleton_memory_sequential_queue_factory() -> SingletonMemorySequentialQueueFactory:
	return SingletonMemorySequentialQueueFactory()


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

	def test_keep_reader_alive_and_dispose(self):

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

		def read_thread_method(read_only_async_handle: ReadOnlyAsyncHandle):
			nonlocal sequential_queue_reader
			try:
				sequential_queue_reader.read_bytes()
			except Exception as ex:
				print(f"read_thread_method: ex: {ex}")

		read_async_handle = AsyncHandle(
			get_result_method=read_thread_method
		)
		read_async_handle.try_wait(
			timeout_seconds=1
		)

		sequential_queue.dispose()

	def test_keep_multiple_readers_alive_and_dispose(self):

		sequential_queue_factory = get_default_singleton_memory_sequential_queue_factory()

		sequential_queue = sequential_queue_factory.get_sequential_queue()

		sequential_queue_readers = [
			sequential_queue.get_reader().get_result(),
			sequential_queue.get_reader().get_result()
		]  # type: List[SingletonMemorySequentialQueueReader]

		def read_thread_method(read_only_async_handle: ReadOnlyAsyncHandle, reader: SingletonMemorySequentialQueueReader):
			try:
				reader.read_bytes()
			except Exception as ex:
				print(f"read_thread_method: ex: {ex}")

		for reader in sequential_queue_readers:
			read_async_handle = AsyncHandle(
				get_result_method=read_thread_method,
				reader=reader
			)
			read_async_handle.try_wait(
				timeout_seconds=1
			)

		sequential_queue.dispose()

	def test_ensure_multiple_readers_closed_and_dispose(self):

		sequential_queue_factory = get_default_singleton_memory_sequential_queue_factory()

		sequential_queue = sequential_queue_factory.get_sequential_queue()

		sequential_queue_readers = [
			sequential_queue.get_reader().get_result(),
			sequential_queue.get_reader().get_result()
		]  # type: List[SingletonMemorySequentialQueueReader]

		sequential_queue.dispose()
