import unittest
from datetime import datetime
from src.austin_heller_repo.threading import TimeoutThread, time, ThreadDelay, Semaphore, SemaphoreRequestQueue, start_thread, SemaphoreRequest, PreparedSemaphoreRequest, CyclingUnitOfWork, ThreadCycle, ThreadCycleCache, BooleanReference, AsyncHandle, ReadOnlyAsyncHandle
from typing import List, Tuple, Dict


class ThreadingTest(unittest.TestCase):

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
                #print(f"{_sleep_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: sleeping for {_sleep_seconds[_sleep_index]}")
                _start_datetime = datetime.utcnow()
                _is_sleep_completed_normally = _thread_delay.try_sleep(
                    seconds=_sleep_seconds[_sleep_index]
                )
                _end_datetime = datetime.utcnow()
                _difference = round((_end_datetime - _start_datetime).total_seconds() * 2)/2
                _actual_sleep_outcome.append((_difference, _is_sleep_completed_normally))
                #print(f"{_sleep_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: sleep {_is_sleep_completed_normally}")
                _sleep_index += 1

        def _abort():
            for _abort_index in range(len(_abort_seconds)):
                #print(f"{_abort_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: aborting after {_abort_seconds[_abort_index]}")
                _start_datetime = datetime.utcnow()
                time.sleep(_abort_seconds[_abort_index])
                _is_sleep_aborted = _thread_delay.try_abort()
                _end_datetime = datetime.utcnow()
                _difference = round((_end_datetime - _start_datetime).total_seconds() * 2)/2
                _actual_abort_outcome.append((_difference, _is_sleep_aborted))
                #print(f"{_abort_index}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}: aborted {_is_sleep_aborted}")
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
                        release_semaphore_names=[]
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
                        release_semaphore_names=[]
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
                        release_semaphore_names=["test"]
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
                        release_semaphore_names=["release"]
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
                        release_semaphore_names=[]
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
                        release_semaphore_names=["test"]
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

    def test_semaphore_request_queue_2(self):
        # test swapping of two semaphores

        _expected_orders = [
            ["first start", "first end", "second start", "third start", "fourth start", "fourth end", "third end", "fifth start", "fifth end", "second end"],
            ["first start", "first end", "second start", "third start", "fourth start", "fourth end", "third end", "fifth start", "second end", "fifth end"],
            ["first start", "first end", "second start", "third start", "fourth start", "third end", "fourth end", "fifth start", "fifth end", "second end"],
            ["first start", "first end", "second start", "third start", "fourth start", "third end", "fourth end", "fifth start", "second end", "fifth end"]
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
                        release_semaphore_names=[]
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
                        acquire_semaphore_names=["first", "second"],
                        release_semaphore_names=[]
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
                        acquire_semaphore_names=["first"],
                        release_semaphore_names=["second"]
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
                        release_semaphore_names=["first"]
                    )
                )

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
                        release_semaphore_names=["first"]
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

                def perform(self, *, try_get_next_work_queue_element_prepared_semaphore_request: PreparedSemaphoreRequest, acknowledge_nonempty_work_queue_prepared_semaphore_request: PreparedSemaphoreRequest) -> bool:
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

            def perform(self, *, try_get_next_work_queue_element_prepared_semaphore_request: PreparedSemaphoreRequest, acknowledge_nonempty_work_queue_prepared_semaphore_request: PreparedSemaphoreRequest) -> bool:
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

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):
            nonlocal stage_index

            for index in range(10):
                if read_only_async_handle.is_cancelled():
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

    def test_exception_in_async_handle_01(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        time.sleep(1)

        with self.assertRaises(Exception) as ex:
            async_handle.get_result()

        self.assertEqual("test exception", str(ex.exception))

    def test_exception_in_async_handle_02(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            time.sleep(1)

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        with self.assertRaises(Exception) as ex:
            async_handle.get_result()

        self.assertEqual("test exception", str(ex.exception))

    def test_exception_in_async_handle_03(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        with self.assertRaises(Exception) as ex:
            async_handle.try_wait(
                timeout_seconds=1
            )

        self.assertEqual("test exception", str(ex.exception))

    def test_exception_in_async_handle_04(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            time.sleep(1)

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        self.assertFalse(async_handle.try_wait(
            timeout_seconds=0.5
        ))

        time.sleep(1)

        with self.assertRaises(Exception) as ex:
            async_handle.try_wait(
                timeout_seconds=0.5
            )

        self.assertEqual("test exception", str(ex.exception))

    def test_exception_in_async_handle_05(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            time.sleep(1)

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        time.sleep(0.5)

        async_handle.cancel()

        time.sleep(1)

        self.assertTrue(async_handle.try_wait(
            timeout_seconds=0
        ))

    def test_exception_in_async_handle_06(self):

        def get_result(read_only_async_handle: ReadOnlyAsyncHandle):

            time.sleep(1)

            raise Exception(f"test exception")

        async_handle = AsyncHandle(
            get_result_method=get_result
        )

        self.assertFalse(async_handle.try_wait(
            timeout_seconds=0.5
        ))

        time.sleep(1)

        with self.assertRaises(Exception) as ex:
            async_handle.get_result()

        self.assertEqual("test exception", str(ex.exception))

    def test_parent_child_async_handles(self):

        def method_0(read_only_async_handle: ReadOnlyAsyncHandle):

            def inner_method(read_only_async_handle: ReadOnlyAsyncHandle):

                time.sleep(1)

            async_handle = AsyncHandle(
                get_result_method=inner_method
            )

            async_handle.add_parent(read_only_async_handle)

            async_handle.get_result()

        async_handle = AsyncHandle(
            get_result_method=method_0
        )

        async_handle.get_result()
