import unittest
from src.austin_heller_repo.threading import WindowBuffer, ByteArrayBufferFactory, UuidGeneratorFactory, UuidGenerator, ListBufferFactory, start_thread, TimeoutThread, ThreadDelay, SemaphoreRequest, Semaphore, SemaphoreRequestQueue, CyclingUnitOfWork, ThreadCycleCache, ThreadCycle, PreparedSemaphoreRequest, BooleanReference, AsyncHandle
import uuid
import time
from datetime import datetime
from typing import List


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

    def test_thread_delay_0(self):
        # test starting and stopping multiple times
        _thread_delay = ThreadDelay()
        _is_sleeping = True
        _is_aborting = True
        _abort_seconds = [0.5, 1.5, 0.5]
        _sleep_seconds = [1.0, 1.0, 1.0, 1.0]

        # sleep  ---!-------#---!---!-------#
        # abort  ---#-----------#---#
        #       0   .   1   .   2   .   3

        _expected_abort_outcome = [
            (0.5, True),
            (1.5, True),
            (0.5, True)
        ]
        _expected_sleep_outcome = [
            (0.5, False),
            (1.0, True),
            (0.5, False),
            (0.5, False)
        ]

        _actual_abort_outcome = []  # type: List[Tuple[float, bool]]
        _actual_sleep_outcome = []  # type: List[Tuple[float, bool]]

        def _sleep():
            for _sleep_index in range(len(_sleep_seconds)):
                # print(f"{_sleep_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: sleeping for {_sleep_seconds[_sleep_index]}")
                _start_datetime = datetime.utcnow()
                _is_sleep_completed_normally = _thread_delay.try_sleep(
                    seconds=_sleep_seconds[_sleep_index]
                )
                _end_datetime = datetime.utcnow()
                _difference = round((_end_datetime - _start_datetime).total_seconds() * 2) / 2
                _actual_sleep_outcome.append((_difference, _is_sleep_completed_normally))
                # print(f"{_sleep_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: sleep {_is_sleep_completed_normally}")
                _sleep_index += 1

        def _abort():
            for _abort_index in range(len(_abort_seconds)):
                # print(f"{_abort_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: aborting after {_abort_seconds[_abort_index]}")
                _start_datetime = datetime.utcnow()
                time.sleep(_abort_seconds[_abort_index])
                _is_sleep_aborted = _thread_delay.try_abort()
                _end_datetime = datetime.utcnow()
                _difference = round((_end_datetime - _start_datetime).total_seconds() * 2) / 2
                _actual_abort_outcome.append((_difference, _is_sleep_aborted))
                # print(f"{_abort_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: aborted {_is_sleep_aborted}")
                _abort_index += 1

        _sleep_thread = start_thread(_sleep)
        _abort_thread = start_thread(_abort)

        time.sleep(2.6)

        self.assertEqual(len(_expected_sleep_outcome), len(_actual_sleep_outcome))
        self.assertEqual(len(_expected_abort_outcome), len(_actual_abort_outcome))

        for _index in range(len(_expected_sleep_outcome)):
            self.assertEqual(_expected_sleep_outcome[_index], _actual_sleep_outcome[_index])

        for _index in range(len(_expected_abort_outcome)):
            self.assertEqual(_expected_abort_outcome[_index], _actual_abort_outcome[_index])

    def test_semaphore_request_queue_0(self):

        _expected_orders = [
            ["first start", "first end", "second start", "third start", "second end", "third end"],
            ["first start", "first end", "second start", "third start", "third end", "second end"]
        ]

        _actual_orders = []

        for _trial_index in range(100):
            _semaphore_request_queue = SemaphoreRequestQueue(
                acquired_semaphore_names=[]
            )

            _order = []
            _order_semaphore = Semaphore()

            def _first_thread_method():
                _order_semaphore.acquire()
                _order.append("first start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["test"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("first end")
                _order_semaphore.release()

            def _second_thread_method():
                _order_semaphore.acquire()
                _order.append("second start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["test"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("second end")
                _order_semaphore.release()

            def _third_thread_method():
                _order_semaphore.acquire()
                _order.append("third start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["test"],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("third end")
                _order_semaphore.release()

            _first_thread = start_thread(_first_thread_method)

            time.sleep(0.05)

            _second_thread = start_thread(_second_thread_method)

            time.sleep(0.05)

            _third_thread = start_thread(_third_thread_method)

            time.sleep(0.05)

            _actual_orders.append(_order)

        for _actual_order in _actual_orders:
            self.assertIn(_actual_order, _expected_orders)

    def test_semaphore_request_queue_1(self):

        _expected_orders = [
            ["first start", "second start", "second end", "first end", "third start", "third end"],
            ["first start", "second start", "first end", "second end", "third start", "third end"]
        ]

        _actual_orders = []

        for _trial_index in range(100):
            _semaphore_request_queue = SemaphoreRequestQueue(
                acquired_semaphore_names=[]
            )

            _order = []
            _order_semaphore = Semaphore()

            def _first_thread_method():
                _order_semaphore.acquire()
                _order.append("first start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["test"],
                        release_semaphore_names=["release"],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("first end")
                _order_semaphore.release()

            def _second_thread_method():
                _order_semaphore.acquire()
                _order.append("second start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["release"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("second end")
                _order_semaphore.release()

            def _third_thread_method():
                _order_semaphore.acquire()
                _order.append("third start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["test"],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("third end")
                _order_semaphore.release()

            _first_thread = start_thread(_first_thread_method)

            time.sleep(0.05)

            _second_thread = start_thread(_second_thread_method)

            time.sleep(0.05)

            _third_thread = start_thread(_third_thread_method)

            time.sleep(0.05)

            _actual_orders.append(_order)

        for _actual_order in _actual_orders:
            self.assertIn(_actual_order, _expected_orders)

    def test_semaphore_request_queue_3(self):
        # test swapping of two semaphores without using async release

        _expected_orders = [
            ["first start", "first end", "second start", "third start", "fourth start", "second end", "third end", "fourth end", "fifth start", "fifth end"]
        ]

        _actual_orders = []

        for _trial_index in range(100):
            _semaphore_request_queue = SemaphoreRequestQueue(
                acquired_semaphore_names=[]
            )

            _order = []
            _order_semaphore = Semaphore()

            def _first_thread_method():
                _order_semaphore.acquire()
                _order.append("first start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["first", "second"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("first end")
                _order_semaphore.release()

            def _second_thread_method():
                _order_semaphore.acquire()
                _order.append("second start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["first"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("second end")
                _order_semaphore.release()

            def _third_thread_method():
                _order_semaphore.acquire()
                _order.append("third start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["second"],
                        release_semaphore_names=["first"],
                        is_release_async=False
                    )
                )

                time.sleep(0.01)

                _order_semaphore.acquire()
                _order.append("third end")
                _order_semaphore.release()

            def _fourth_thread_method():
                _order_semaphore.acquire()
                _order.append("fourth start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["second"],
                        is_release_async=False
                    )
                )

                time.sleep(0.02)

                _order_semaphore.acquire()
                _order.append("fourth end")
                _order_semaphore.release()

            def _fifth_thread_method():
                _order_semaphore.acquire()
                _order.append("fifth start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["first", "second"],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("fifth end")
                _order_semaphore.release()

            _first_thread = start_thread(_first_thread_method)

            time.sleep(0.05)

            _second_thread = start_thread(_second_thread_method)

            time.sleep(0.05)

            _third_thread = start_thread(_third_thread_method)

            time.sleep(0.05)

            _fourth_thread = start_thread(_fourth_thread_method)

            time.sleep(0.05)

            _fifth_thread = start_thread(_fifth_thread_method)

            time.sleep(0.05)

            _actual_orders.append(_order)

        for _actual_order in _actual_orders:
            self.assertIn(_actual_order, _expected_orders)

    def test_semaphore_request_queue_4(self):
        # test swapping of two semaphores with using async release

        _expected_orders = [
            ["first start", "first end", "second start", "third start", "second end", "fourth start", "third end", "fourth end", "fifth start", "fifth end"]
        ]

        _actual_orders = []

        for _trial_index in range(100):
            _semaphore_request_queue = SemaphoreRequestQueue(
                acquired_semaphore_names=[]
            )

            _order = []
            _order_semaphore = Semaphore()

            def _first_thread_method():
                _order_semaphore.acquire()
                _order.append("first start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["first", "second"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("first end")
                _order_semaphore.release()

            def _second_thread_method():
                _order_semaphore.acquire()
                _order.append("second start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["first"],
                        release_semaphore_names=[],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("second end")
                _order_semaphore.release()

            def _third_thread_method():
                _order_semaphore.acquire()
                _order.append("third start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=["second"],
                        release_semaphore_names=["first"],
                        is_release_async=True
                    )
                )

                _order_semaphore.acquire()
                _order.append("third end")
                _order_semaphore.release()

            def _fourth_thread_method():
                _order_semaphore.acquire()
                _order.append("fourth start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["second"],
                        is_release_async=False
                    )
                )

                time.sleep(0.01)

                _order_semaphore.acquire()
                _order.append("fourth end")
                _order_semaphore.release()

            def _fifth_thread_method():
                _order_semaphore.acquire()
                _order.append("fifth start")
                _order_semaphore.release()

                _semaphore_request_queue.enqueue(
                    semaphore_request=SemaphoreRequest(
                        acquire_semaphore_names=[],
                        release_semaphore_names=["first", "second"],
                        is_release_async=False
                    )
                )

                _order_semaphore.acquire()
                _order.append("fifth end")
                _order_semaphore.release()

            _first_thread = start_thread(_first_thread_method)

            time.sleep(0.05)

            _second_thread = start_thread(_second_thread_method)

            time.sleep(0.05)

            _third_thread = start_thread(_third_thread_method)

            time.sleep(0.05)

            _fourth_thread = start_thread(_fourth_thread_method)

            time.sleep(0.05)

            _fifth_thread = start_thread(_fifth_thread_method)

            time.sleep(0.05)

            _actual_orders.append(_order)

        for _actual_order in _actual_orders:
            self.assertIn(_actual_order, _expected_orders)

    def test_thread_cycle_0(self):

        _exceptions = []

        def _on_exception(ex):
            print(f"ex: {ex}")
            _exceptions.append(ex)

        for _trial_index in range(10):

            _order = []
            _order_semaphore = Semaphore()

            _work_queue = [
                0.1,
                0.1,
                0.1
            ]
            _work_queue_semaphore = Semaphore()

            class TestCyclingUnitOfWork(CyclingUnitOfWork):

                def __init__(self, *, index: int):
                    self.__index = index

                def perform(self, *,
                            try_get_next_work_queue_element_prepared_semaphore_request: PreparedSemaphoreRequest,
                            acknowledge_nonempty_work_queue_prepared_semaphore_request: PreparedSemaphoreRequest) -> bool:
                    try_get_next_work_queue_element_prepared_semaphore_request.apply()
                    _work_queue_semaphore.acquire()
                    _is_successful = False
                    if len(_work_queue) != 0:
                        _work_queue_element = _work_queue.pop(0)
                        time.sleep(_work_queue_element)
                        _order_semaphore.acquire()
                        _order.append(self.__index)
                        _order_semaphore.release()
                        _is_successful = True
                        acknowledge_nonempty_work_queue_prepared_semaphore_request.apply()
                    _work_queue_semaphore.release()
                    return _is_successful

            _thread_cycle = ThreadCycle(
                cycling_unit_of_work=TestCyclingUnitOfWork(
                    index=0
                ),
                on_exception=_on_exception
            )

            time.sleep(0.5)

            self.assertEqual([], _order)

            _thread_cycle.start()

            self.assertEqual([], _order)

            _cycled = _thread_cycle.try_cycle()

            self.assertEqual(True, _cycled)

            time.sleep(0.5)

            self.assertEqual([0, 0, 0], _order)

            _work_queue.extend([
                0.1,
                0.1,
                0.1
            ])

            _cycled = _thread_cycle.try_cycle()

            self.assertEqual(True, _cycled)

            _cycled = _thread_cycle.try_cycle()

            self.assertEqual(False, _cycled)

            time.sleep(0.5)

            self.assertEqual([0, 0, 0, 0, 0, 0], _order)

            _thread_cycle.stop()

        self.assertEqual(0, len(_exceptions))

    def test_thread_cycle_cache_0(self):

        _order = []
        _order_semaphore = Semaphore()

        _work_queue = [
            0.1,
            0.1,
            0.1
        ]
        _work_queue_semaphore = Semaphore()

        class TestCyclingUnitOfWork(CyclingUnitOfWork):

            def __init__(self, *, index: int):
                super().__init__()

                self.__index = index

            def perform(self, *, try_get_next_work_queue_element_prepared_semaphore_request: PreparedSemaphoreRequest,
                        acknowledge_nonempty_work_queue_prepared_semaphore_request: PreparedSemaphoreRequest) -> bool:
                try_get_next_work_queue_element_prepared_semaphore_request.apply()
                _work_queue_semaphore.acquire()
                _is_successful = False
                if len(_work_queue) != 0:
                    _work_queue_element = _work_queue.pop(0)
                    time.sleep(_work_queue_element)
                    _order_semaphore.acquire()
                    _order.append(self.__index)
                    _order_semaphore.release()
                    _is_successful = True
                    acknowledge_nonempty_work_queue_prepared_semaphore_request.apply()
                _work_queue_semaphore.release()
                return _is_successful

        _exceptions = []

        def _on_exception(ex):
            print(f"ex: {ex}")
            _exceptions.append(ex)

        _thread_cycle_cache = ThreadCycleCache(
            cycling_unit_of_work=TestCyclingUnitOfWork(
                index=0
            ),
            on_exception=_on_exception
        )

        _is_added = []  # type: List[bool]
        for _index in range(len(_work_queue) + 1):
            _is_added.append(_thread_cycle_cache.try_add())

        self.assertEqual([True, True, True, False], _is_added)

        _thread_cycle_cache.clear()

        self.assertEqual(0, len(_exceptions))

    def test_timeout_thread_0(self):
        # will timeout

        def _thread_method():
            time.sleep(2.0)

        _timeout_thread = TimeoutThread(
            target=_thread_method,
            timeout_seconds=1.0
        )

        _timeout_thread.start()

        _wait_is_successful = _timeout_thread.try_wait()

        self.assertFalse(_wait_is_successful)

        _join_is_successful = _timeout_thread.try_join()

        self.assertEqual(_wait_is_successful, _join_is_successful)

    def test_timeout_thread_1(self):
        # will not timeout

        def _thread_method():
            time.sleep(1.0)

        _timeout_thread = TimeoutThread(
            target=_thread_method,
            timeout_seconds=2.0
        )

        _timeout_thread.start()

        _wait_is_successful = _timeout_thread.try_wait()

        self.assertTrue(_wait_is_successful)

        _join_is_successful = _timeout_thread.try_join()

        self.assertEqual(_wait_is_successful, _join_is_successful)

    def test_timeout_thread_2(self):
        # will be on the line between timeout or not

        def _thread_method():
            time.sleep(0.099)

        _outcomes = []
        for _index in range(100):
            _timeout_thread = TimeoutThread(
                target=_thread_method,
                timeout_seconds=0.1
            )

            _timeout_thread.start()

            _wait_is_successful = _timeout_thread.try_wait()

            _outcomes.append(_wait_is_successful)

            _join_is_successful = _timeout_thread.try_join()

            self.assertEqual(_wait_is_successful, _join_is_successful)

        _is_successful_true_total = len([_outcome for _outcome in _outcomes if _outcome])
        _is_successful_false_total = len([_outcome for _outcome in _outcomes if not _outcome])
        print(f"True: {_is_successful_true_total}, False: {_is_successful_false_total}")

        self.assertGreater(_is_successful_true_total, _is_successful_false_total)

    def test_cancel_async_handle(self):

        stage_index = 0

        def get_result(is_cancelled: BooleanReference):
            nonlocal stage_index

            for index in range(10):
                if is_cancelled.get():
                    break
                else:
                    stage_index += 1
                    time.sleep(1.0)

            return "Done"

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        first_wait_is_successful = async_handle.try_wait(
            timeout_seconds=5.5
        )
        self.assertFalse(first_wait_is_successful)

        async_handle.cancel()

        start_time = datetime.utcnow()
        second_wait_is_successful = async_handle.try_wait(
            timeout_seconds=5
        )
        end_time = datetime.utcnow()

        self.assertTrue(second_wait_is_successful)

        total_time = (end_time - start_time).total_seconds()
        self.assertLess(total_time, 5)

        result = async_handle.get_result()

        self.assertIsNone(result)

        time.sleep(6)

        after_true_wait_result = async_handle.get_result()

        self.assertEqual("Done", after_true_wait_result)
        self.assertEqual(6, stage_index)
