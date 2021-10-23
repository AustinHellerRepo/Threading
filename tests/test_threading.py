import unittest
from src.austin_heller_repo.threading import WindowBuffer, ByteArrayBufferFactory, UuidGeneratorFactory, UuidGenerator, ListBufferFactory, start_thread
import uuid
import time


class PythonUuidGenerator(UuidGenerator):

    def get_uuid(self) -> str:
        return str(uuid.uuid4())


class PythonUuidGeneratorFactory(UuidGeneratorFactory):

    def get_uuid_generator(self) -> UuidGenerator:
        return PythonUuidGenerator()


class TestThreading(unittest.TestCase):

    def test_window_buffer_0(self):
        # initialize
        _window_buffer = WindowBuffer(
            buffer_factory=ByteArrayBufferFactory(),
            uuid_generator_factory=PythonUuidGeneratorFactory()
        )

    def test_window_buffer_1(self):
        # initialize, extend, get_buffer, get_window, push_window, get_buffer
        _window_buffer = WindowBuffer(
            buffer_factory=ByteArrayBufferFactory(),
            uuid_generator_factory=PythonUuidGeneratorFactory()
        )
        _item = b"12345678"
        _window_buffer.extend(_item)
        _buffer = _window_buffer.get_buffer()
        self.assertEqual(_item, _buffer)
        _window = _window_buffer.get_window(4)
        self.assertEqual(_item[:4], _window)
        _window_buffer.push_window(4)
        _remaining_buffer = _window_buffer.get_buffer()
        self.assertEqual(_item[4:], _remaining_buffer)
        _window_buffer.dispose()

    def test_window_buffer_2(self):
        # initialize, start threads to append/extend
        _window_buffer = WindowBuffer(
            buffer_factory=ListBufferFactory(),
            uuid_generator_factory=PythonUuidGeneratorFactory()
        )

        _is_running = True

        def _append_thread_method():
            nonlocal _window_buffer
            nonlocal _is_running

            _index = 0
            while _is_running:
                _window_buffer.append(_index)
                time.sleep(0.1)
                _index += 1

        self.assertEqual([], _window_buffer.get_buffer())
        _thread = start_thread(_append_thread_method)
        time.sleep(0.05)
        self.assertEqual([0], _window_buffer.get_buffer())
        time.sleep(0.1)
        self.assertEqual([0, 1], _window_buffer.get_buffer())
        time.sleep(0.1)
        self.assertEqual([0, 1, 2], _window_buffer.get_buffer())
        _is_running = False
        time.sleep(0.1)
        self.assertEqual([0, 1, 2], _window_buffer.get_buffer())
        _thread.join()
        self.assertEqual([0, 1, 2], _window_buffer.get_buffer())

    def test_window_buffer_3(self):
        # initialize, append and attempt to push then request data
        _window_buffer = WindowBuffer(
            buffer_factory=ListBufferFactory(),
            uuid_generator_factory=PythonUuidGeneratorFactory()
        )

        _is_running = True
        _times_requested_total = 0
        _times_pushed_total = 0

        def _append_thread_method():
            nonlocal _window_buffer
            nonlocal _is_running

            _index = 0
            while _is_running:
                print(f"test_window_buffer_3: _append_thread_method: {_index}")
                _window_buffer.append(_index)
                time.sleep(0.1)
                _index += 1

        def _request_push_thread_method():
            nonlocal _window_buffer
            nonlocal _is_running
            nonlocal _times_requested_total
            nonlocal _times_pushed_total
            print("test_window_buffer_3: _request_push_thread_method: while _is_running:")
            while _is_running:
                print("test_window_buffer_3: _request_push_thread_method: _window_buffer.get_window(3)")
                _window_buffer.get_window(3)
                print("test_window_buffer_3: _request_push_thread_method: _times_requested_total += 1")
                _times_requested_total += 1
                print("test_window_buffer_3: _request_push_thread_method: if _is_running:")
                if _is_running:
                    print("test_window_buffer_3: _request_push_thread_method: _window_buffer.push_window(6)")
                    _window_buffer.push_window(6)
                    print("test_window_buffer_3: _request_push_thread_method: _times_pushed_total += 1")
                    _times_pushed_total += 1

        print("test_window_buffer_3: verify fresh test")
        self.assertEqual(0, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([], _window_buffer.get_buffer())
        _append_thread = start_thread(_append_thread_method)
        _request_push_thread = start_thread(_request_push_thread_method)
        time.sleep(0.05)  # put the checks in the middle
        print("test_window_buffer_3: test wait 1")
        self.assertEqual(0, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([0], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 2")
        self.assertEqual(0, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([0, 1], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 3")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([0, 1, 2], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 4")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([0, 1, 2, 3], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 5")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(0, _times_pushed_total)
        self.assertEqual([0, 1, 2, 3, 4], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 6")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(1, _times_pushed_total)
        self.assertEqual([], _window_buffer.get_buffer())
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 7")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(1, _times_pushed_total)
        self.assertEqual([6], _window_buffer.get_buffer())
        _is_running = False
        time.sleep(0.1)
        print("test_window_buffer_3: test wait 8")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(1, _times_pushed_total)
        self.assertEqual([6], _window_buffer.get_buffer())
        _window_buffer.dispose()
        _append_thread.join()
        _request_push_thread.join()
        print("test_window_buffer_3: test wait 9")
        self.assertEqual(1, _times_requested_total)
        self.assertEqual(1, _times_pushed_total)
        self.assertEqual([6], _window_buffer.get_buffer())
