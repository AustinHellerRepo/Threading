import gc
import time

try:
	import threading

	def start_thread(target, *args, **kwargs):
		_thread = threading.Thread(target=target, args=args, kwargs=kwargs)
		_thread.start()
		return _thread

	class Semaphore():

		def __init__(self):
			self.__lock = threading.Semaphore()

		def acquire(self):
			self.__lock.acquire()

		def release(self):
			self.__lock.release()

except ImportError:
	try:
		import _thread as threading

		def start_thread(target, *args, **kwargs):
			def _thread_method():
				target(*args, **kwargs)
			_thread = threading.start_new_thread(_thread_method, ())
			return _thread

		class Semaphore():

			def __init__(self):
				self.__lock = threading.allocate_lock()

			def acquire(self):
				self.__lock.acquire()

			def release(self):
				self.__lock.release()

	except ImportError:
		gc.collect()

		def start_thread(target, *args, **kwargs):
			target(*args, **kwargs)
			return None
		_is_threading_async = False

		class Semaphore():

			def __init__(self):
				self.__locks_total = 0

			def acquire(self):
				self.__locks_total += 1
				while self.__locks_total > 1:
					time.sleep(0.1)

			def release(self):
				self.__locks_total -= 1
				if self.__locks_total < 0:
					raise Exception("Unexpected number of releases.")


class BooleanReference():

	def __init__(self, value: bool):
		self.__value = value

	def get(self) -> bool:
		return self.__value

	def set(self, value: bool):
		self.__value = value


class StringReference():

	def __init__(self, value: str):
		self.__value = value

	def get(self) -> str:
		return self.__value

	def set(self, value: str):
		self.__value = value


class ThreadDelay():

	def __init__(self):

		self.__is_sleeping = False
		self.__is_sleeping_semaphore = Semaphore()
		self.__is_aborted = None  # type: BooleanReference
		self.__is_completed = None  # type: BooleanReference
		self.__sleep_block_semaphore = Semaphore()

	def try_sleep(self, *, seconds: float) -> bool:

		self.__is_sleeping_semaphore.acquire()
		_is_already_sleeping = None
		if not self.__is_sleeping:
			self.__is_sleeping = True
			self.__is_aborted = BooleanReference(False)
			self.__is_completed = BooleanReference(False)
			_is_already_sleeping = False
		else:
			_is_already_sleeping = True
		self.__is_sleeping_semaphore.release()

		if _is_already_sleeping:
			raise Exception("ThreadDelay instance already used for sleeping.")
		else:

			_is_completed_normally = False
			_is_aborted = self.__is_aborted  # type: BooleanReference
			_is_completed = self.__is_completed  # type: BooleanReference

			def _sleep_thread_method():
				nonlocal _is_completed_normally
				nonlocal seconds
				nonlocal _is_aborted
				nonlocal _is_completed
				time.sleep(seconds)
				self.__is_sleeping_semaphore.acquire()
				if not _is_aborted.get() and not _is_completed.get():
					_is_completed_normally = True
					_is_completed.set(True)
					self.__is_sleeping = False
					self.__sleep_block_semaphore.release()
				self.__is_sleeping_semaphore.release()

			self.__sleep_block_semaphore.acquire()
			_sleep_thread = start_thread(_sleep_thread_method)

			self.__sleep_block_semaphore.acquire()
			self.__sleep_block_semaphore.release()

			return _is_completed_normally

	def try_abort(self) -> bool:

		self.__is_sleeping_semaphore.acquire()
		_is_aborted = False
		if self.__is_sleeping:
			if not self.__is_aborted.get() and not self.__is_completed.get():
				self.__is_aborted.set(True)
				self.__is_sleeping = False
				_is_aborted = True
				self.__sleep_block_semaphore.release()
		self.__is_sleeping_semaphore.release()

		return _is_aborted


class EncapsulatedThread():

	def __init__(self, *, target, is_running_boolean_reference: BooleanReference, polling_thread_delay: ThreadDelay, error_string_reference: StringReference):

		self.__target = target
		self.__is_running_boolean_reference = is_running_boolean_reference
		self.__polling_thread_delay = polling_thread_delay
		self.__error_string_reference = error_string_reference

		self.__thread = None

	def start(self):

		if self.__thread is not None:
			raise Exception("Must first stop before starting.")

		self.__thread = start_thread(self.__target)

	def stop(self):

		self.__is_running_boolean_reference.set(False)
		self.__polling_thread_delay.try_abort()
		self.__thread.join()
		self.__thread = None

	def get_last_error(self) -> str:
		return self.__error_string_reference.get()


class SemaphoreRequest():

	def __init__(self, *, acquire_semaphore_names: list, release_semaphore_names: list, is_release_async: bool):

		self.__acquire_semaphore_names = acquire_semaphore_names
		self.__release_semaphore_names = release_semaphore_names
		self.__is_release_async = is_release_async

	def get_aquire_semaphore_names(self):
		return self.__acquire_semaphore_names

	def get_release_semaphore_names(self):
		return self.__release_semaphore_names

	def get_is_release_async(self) -> bool:
		return self.__is_release_async

	def clear_release_semaphore_names(self):
		self.__release_semaphore_names.clear()


class SemaphoreRequestQueue():

	def __init__(self, *, acquired_semaphore_names):

		self.__acquired_semaphore_names = acquired_semaphore_names

		self.__enqueue_semaphore = Semaphore()
		self.__active_queue = []  # this queue is holding semaphore requests that have not yet been attempted
		self.__pending_queue = []  # this queue is holding semaphore requests that were already tried and could not be completed yet
		self.__queue_semaphore = Semaphore()
		self.__dequeue_semaphore = Semaphore()

	def enqueue(self, *, semaphore_request: SemaphoreRequest):

		self.__enqueue_semaphore.acquire()

		_blocking_semaphore = Semaphore()
		_blocking_semaphore.acquire()

		self.__queue_semaphore.acquire()
		self.__active_queue.append((semaphore_request, _blocking_semaphore))
		if len(self.__active_queue) == 1:
			_dequeue_thread = start_thread(self.__dequeue_thread_method)
		self.__queue_semaphore.release()

		self.__enqueue_semaphore.release()

		_blocking_semaphore.acquire()
		_blocking_semaphore.release()

	def __dequeue_thread_method(self):

		def _try_process_semaphore_request(*, semaphore_request: SemaphoreRequest):
			# can this semaphore request acquire the necessary semaphores?
			_is_at_least_one_acquired_semaphore = False
			_is_at_least_one_released_semaphore = False
			for _acquire_semaphore_name in semaphore_request.get_aquire_semaphore_names():
				if _acquire_semaphore_name in self.__acquired_semaphore_names:
					# this acquire semaphore name is already acquired, so it cannot be acquired again
					_is_at_least_one_acquired_semaphore = True
					break
			if not _is_at_least_one_acquired_semaphore or semaphore_request.get_is_release_async():
				# can this semaphore request release the necessary semaphores?
				for _release_semaphore_name in semaphore_request.get_release_semaphore_names():
					if _release_semaphore_name not in self.__acquired_semaphore_names:
						# this release semaphore name is not currently acquired, so it cannot be released
						_is_at_least_one_released_semaphore = True
						break

			print(f"semaphore_request: {semaphore_request.get_aquire_semaphore_names()} | {semaphore_request.get_release_semaphore_names()} | {semaphore_request.get_is_release_async()}")
			print(f"_is_at_least_one_acquired_semaphore: {_is_at_least_one_acquired_semaphore}")
			print(f"_is_at_least_one_released_semaphore: {_is_at_least_one_released_semaphore}")

			if not semaphore_request.get_is_release_async():
				if not _is_at_least_one_acquired_semaphore and not _is_at_least_one_released_semaphore:
					self.__acquired_semaphore_names.extend(semaphore_request.get_aquire_semaphore_names())
					for _release_semaphore_name in semaphore_request.get_release_semaphore_names():
						self.__acquired_semaphore_names.remove(_release_semaphore_name)
					print(f"return True, True")
					return True, True  # was this semaphore acquired, did this semaphore alter the state
				print(f"return False, False")
				return False, False
			else:
				if not _is_at_least_one_released_semaphore:  # the semaphore are acquired and can be released
					for _release_semaphore_name in semaphore_request.get_release_semaphore_names():
						self.__acquired_semaphore_names.remove(_release_semaphore_name)
					if not _is_at_least_one_acquired_semaphore:  # the acquire of semaphores is also possible
						self.__acquired_semaphore_names.extend(semaphore_request.get_aquire_semaphore_names())
						print(f"return True, True")
						return True, True
					else:
						semaphore_request.clear_release_semaphore_names()  # clear out the release semaphores so that they are not stopping the next attempt to acquire
						print(f"return False, True")
						return False, True
				else:
					print(f"return False, False")
					return False, False

		self.__dequeue_semaphore.acquire()

		_is_queue_empty = False
		while not _is_queue_empty:

			# try to process first pending semaphore request

			self.__queue_semaphore.acquire()
			_semaphore_request, _blocking_semaphore = self.__active_queue.pop(0)
			_is_queue_empty = (len(self.__active_queue) == 0)
			self.__queue_semaphore.release()

			print(f"processing active...")
			_is_semaphore_acquired, _is_state_changed = _try_process_semaphore_request(
				semaphore_request=_semaphore_request
			)
			print(f"processed active")

			# if the state changed, then try to process the pended requests
			while _is_state_changed and len(self.__pending_queue) != 0:
				for _pending_queue_index, (_pending_semaphore_request, _pending_blocking_semaphore) in enumerate(self.__pending_queue):
					print(f"processing pended...")
					_is_pended_semaphore_acquired, _is_state_changed = _try_process_semaphore_request(
						semaphore_request=_pending_semaphore_request
					)
					print(f"processed pended")
					if _is_pended_semaphore_acquired:
						print(f"pended acquired")
						_pending_blocking_semaphore.release()
						del self.__pending_queue[_pending_queue_index]
					if _is_state_changed:
						break  # the state has changed, so revisit the earlier queued requests

			# if it could be processed, then release blocking semaphore and run through the pending semaphore requests
			if _is_semaphore_acquired:
				print(f"active acquired")
				_blocking_semaphore.release()
			else:
				self.__pending_queue.append((_semaphore_request, _blocking_semaphore))

		self.__dequeue_semaphore.release()


class PreparedSemaphoreRequest():

	def __init__(self, *, semaphore_request: SemaphoreRequest, semaphore_request_queue: SemaphoreRequestQueue):

		self.__semaphore_request = semaphore_request
		self.__semaphore_request_queue = semaphore_request_queue

	def apply(self):

		self.__semaphore_request_queue.enqueue(
			semaphore_request=self.__semaphore_request
		)


class TimeoutThread():

	def __init__(self, target, timeout_seconds: float):

		self.__target = target
		self.__timeout_seconds = timeout_seconds

		self.__timeout_thread_delay = None  # type: ThreadDelay
		self.__join_semaphore = Semaphore()
		self.__is_timed_out = None
		self.__process_completed_semaphore = Semaphore()
		self.__process_exception = None  # type: Exception

	def start(self, *args, **kwargs):

		self.__join_semaphore.acquire()
		self.__process_completed_semaphore.acquire()

		_truth_semaphore = Semaphore()

		self.__timeout_thread_delay = ThreadDelay()

		self.__is_timed_out = None

		def _timeout_thread_method():

			self.__timeout_thread_delay.try_sleep(
				seconds=self.__timeout_seconds
			)

			_truth_semaphore.acquire()
			if self.__is_timed_out is None:
				self.__is_timed_out = True
				self.__join_semaphore.release()
			_truth_semaphore.release()

		def _process_thread_method():

			try:
				self.__target(*args, **kwargs)
			except Exception as ex:
				self.__process_exception = ex

			_truth_semaphore.acquire()
			if self.__is_timed_out is None:
				self.__is_timed_out = False
				self.__join_semaphore.release()
				self.__timeout_thread_delay.try_abort()
			_truth_semaphore.release()
			self.__process_completed_semaphore.release()

		_timeout_thread = start_thread(_timeout_thread_method)
		_process_thread = start_thread(_process_thread_method)

	def try_wait(self) -> bool:

		self.__join_semaphore.acquire()
		self.__join_semaphore.release()

		if self.__process_exception is not None:
			raise self.__process_exception

		return not self.__is_timed_out

	def try_join(self) -> bool:

		self.__process_completed_semaphore.acquire()
		self.__process_completed_semaphore.release()

		if self.__process_exception is not None:
			raise self.__process_exception

		return not self.__is_timed_out


class AsyncHandle():

	def __init__(self, *, get_result_method):

		self.__get_result_method = get_result_method

		self.__is_cancelled = BooleanReference(False)
		self.__is_storing = None
		self.__result = None
		self.__wait_for_result_semaphore = Semaphore()

	def __store_result(self):

		self.__wait_for_result_semaphore.acquire()
		self.__is_storing = True
		self.__result = self.__get_result_method(self.__is_cancelled)
		self.__is_storing = False
		self.__wait_for_result_semaphore.release()

	def __wait_for_result(self):

		self.__wait_for_result_semaphore.acquire()
		self.__wait_for_result_semaphore.release()

	def cancel(self):

		self.__is_cancelled.set(True)

	def try_wait(self, *, timeout_seconds: float) -> bool:

		is_successful = True
		if not self.__is_cancelled.get():
			if self.__is_storing is None:
				timeout_thread = TimeoutThread(self.__store_result, timeout_seconds)
				timeout_thread.start()
				is_successful = timeout_thread.try_wait()
			elif self.__is_storing:
				timeout_thread = TimeoutThread(self.__wait_for_result, timeout_seconds)
				timeout_thread.start()
				is_successful = timeout_thread.try_wait()

		return is_successful

	def get_result(self) -> object:

		if not self.__is_cancelled.get():
			if self.__is_storing is None:
				self.__store_result()
			elif self.__is_storing:
				self.__wait_for_result_semaphore.acquire()
				self.__wait_for_result_semaphore.release()

		return self.__result


class CyclingUnitOfWork():
	'''
	This class represents a unit of work that can be repeated until it determines that there is no more work to perform.
	'''

	def perform(self, *, try_get_next_work_queue_element_prepared_semaphore_request: PreparedSemaphoreRequest, acknowledge_nonempty_work_queue_prepared_semaphore_request: PreparedSemaphoreRequest) -> bool:
		'''
		This function should call try_get_next_work_queue_element_prepared_semaphore_request prior to determining if there is any work to perform and
			then acknowledge_nonempty_work_queue_prepared_semaphore_request only if it determines that it should perform work.
		This function expects that there is an underlying queue of work details that is being appended to asynchronously. In order to ensure that work
			is addressed as quickly as possible as well as accurately, it is expected that the PreparedSemaphoreRequest instances will be used to facilitate
			with the acquiring/releasing of semaphores that orchestrate the state of cycling in the ThreadCycle.
		:param try_get_next_work_queue_element_prepared_semaphore_request: a PreparedSemaphoreRequest that blocks the ThreadCycle from trying to start another
			cycle if it's already running or informing the user that the ThreadCycle is already cycling.
		:param acknowledge_nonempty_work_queue_prepared_semaphore_request: a PreparedSemaphoreRequest that unblocks the ThreadCycle from permitting the user to
			call try_cycle.
		:return: if it completed a unit of work, signifying that another cycle attempt should be made.
		'''
		raise NotImplementedError()


class ThreadCycle():
	'''
	This class will wait for a call to try_cycle and will then continue to perform the cycling_unit_of_work until it returns False, signifying that there is no more work to perform.
	'''

	def __init__(self, *, cycling_unit_of_work: CyclingUnitOfWork, on_exception):

		self.__cycling_unit_of_work = cycling_unit_of_work
		self.__on_exception = on_exception

		self.__cycle_thread = None
		self.__is_cycle_thread_running = False
		self.__cycle_thread_semaphore = Semaphore()
		self.__cycle_semaphore_request_queue = SemaphoreRequestQueue(
			acquired_semaphore_names=["blocking cycle"]
		)
		self.__block_cycle_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=["blocking cycle"],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__starting_try_cycle_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=["try cycle"],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__finished_try_cycle_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__finished_try_cycle_and_unblock_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle", "blocking cycle"],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__try_get_next_work_queue_element_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=["try cycle"],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__acknowledge_nonempty_work_queue_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__acknowledge_empty_work_queue_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"],
				is_release_async=False
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__is_cycling = False

	def start(self):

		self.__cycle_thread_semaphore.acquire()
		if self.__is_cycle_thread_running:
			_error = "Cycle must be stopped before it is started again."
		else:
			self.__is_cycle_thread_running = True
			self.__cycle_thread = start_thread(self.__cycle_thread_method)
			_error = None
		self.__cycle_thread_semaphore.release()

		if _error is not None:
			raise Exception(_error)

	def stop(self):

		self.__cycle_thread_semaphore.acquire()
		if not self.__is_cycle_thread_running:
			_error = "Cycle must be started before it can be stopped."
		else:
			self.__is_cycle_thread_running = False
			self.try_cycle()
			self.__cycle_thread.join()
			self.__cycle_thread = None
			_error = None
		self.__cycle_thread_semaphore.release()

		if _error is not None:
			raise Exception(_error)

	def try_cycle(self) -> bool:
		# try to start the internal cycle
		# if it is already cycling, return false

		self.__starting_try_cycle_prepared_semaphore_request.apply()
		_is_cycling_started = not self.__is_cycling
		if _is_cycling_started:
			self.__is_cycling = True
			self.__finished_try_cycle_and_unblock_prepared_semaphore_request.apply()
		else:
			self.__finished_try_cycle_prepared_semaphore_request.apply()
		return _is_cycling_started

	def __cycle_thread_method(self):
		while self.__is_cycle_thread_running:
			self.__block_cycle_prepared_semaphore_request.apply()
			_is_work_successful = True
			_is_work_started = False
			while _is_work_successful and self.__is_cycle_thread_running:
				_is_work_started = True
				try:
					_is_work_successful = self.__cycling_unit_of_work.perform(
						try_get_next_work_queue_element_prepared_semaphore_request=self.__try_get_next_work_queue_element_prepared_semaphore_request,
						acknowledge_nonempty_work_queue_prepared_semaphore_request=self.__acknowledge_nonempty_work_queue_prepared_semaphore_request
					)
				except Exception as ex:
					self.__on_exception(ex)
					_is_work_successful = False
			self.__is_cycling = False
			if _is_work_started:
				self.__acknowledge_empty_work_queue_prepared_semaphore_request.apply()


class ThreadCycleCache():

	def __init__(self, *, cycling_unit_of_work: CyclingUnitOfWork, on_exception):

		self.__cycling_unit_of_work = cycling_unit_of_work
		self.__on_exception = on_exception

		self.__thread_cycles = []
		self.__thread_cycles_semaphore = Semaphore()

	def try_add(self) -> bool:

		_is_add_needed = True
		self.__thread_cycles_semaphore.acquire()
		for _thread_cycle_index in range(len(self.__thread_cycles)):
			_thread_cycle = self.__thread_cycles[_thread_cycle_index]  # type: ThreadCycle
			if _thread_cycle.try_cycle():
				_is_add_needed = False

				# move ThreadCycle to end of list while it runs
				self.__thread_cycles.pop(_thread_cycle_index)
				self.__thread_cycles.append(_thread_cycle)

				break

		if _is_add_needed:
			_thread_cycle = ThreadCycle(
				cycling_unit_of_work=self.__cycling_unit_of_work,
				on_exception=self.__on_exception
			)
			_thread_cycle.start()
			if not _thread_cycle.try_cycle():
				self.__thread_cycles_semaphore.release()
				raise Exception("Failed to start and cycle unit of work immediately.")
			self.__thread_cycles.append(_thread_cycle)
		self.__thread_cycles_semaphore.release()
		return _is_add_needed

	def clear(self):

		self.__thread_cycles_semaphore.acquire()
		for _thread_cycle in self.__thread_cycles:
			_thread_cycle.stop()
		self.__thread_cycles.clear()
		self.__thread_cycles_semaphore.release()


class Buffer():

	def get(self):
		raise NotImplementedError()

	def request(self, length: int):
		raise NotImplementedError()

	def push(self, offset: int):
		raise NotImplementedError()

	def length(self) -> int:
		raise NotImplementedError()

	def append(self, element):
		raise NotImplementedError()

	def extend(self, elements):
		raise NotImplementedError()


class ByteArrayBuffer(Buffer):

	def __init__(self):
		self.__byte_array = bytearray()
		self.__length = 0

	def get(self):
		return self.__byte_array.copy()

	def request(self, length: int):
		return self.__byte_array[:length]

	def push(self, offset: int):
		self.__byte_array = self.__byte_array[offset:]

	def length(self) -> int:
		return self.__length

	def append(self, byte):
		self.__byte_array.append(byte)
		self.__length += 1

	def extend(self, bytes):
		self.__byte_array.extend(bytes)
		self.__length += len(bytes)


class ListBuffer(Buffer):

	def __init__(self):
		self.__list = list()
		self.__length = 0

	def get(self):
		_buffer = self.__list.copy()
		return _buffer

	def request(self, length: int):
		_request = self.__list[:length]
		return _request

	def push(self, offset: int):
		self.__list = self.__list[offset:]

	def length(self) -> int:
		return self.__length

	def append(self, item):
		self.__list.append(item)
		self.__length += 1

	def extend(self, items):
		self.__list.extend(items)
		self.__length += len(items)


class BufferFactory():

	def get_buffer(self) -> Buffer:
		raise NotImplementedError()


class ByteArrayBufferFactory(BufferFactory):

	def get_buffer(self) -> ByteArrayBuffer:
		return ByteArrayBuffer()


class ListBufferFactory(BufferFactory):

	def get_buffer(self) -> ListBuffer:
		return ListBuffer()


class UuidGenerator():

	def get_uuid(self) -> str:
		raise NotImplementedError()


class UuidGeneratorFactory():

	def get_uuid_generator(self) -> UuidGenerator:
		raise NotImplementedError()


class DisposedException(Exception):
	pass


class CancelledException(Exception):
	pass


class WindowBuffer():

	def __init__(self, *, buffer_factory: BufferFactory, uuid_generator_factory: UuidGeneratorFactory):

		self.__buffer_factory = buffer_factory
		self.__uuid_generator_factory = uuid_generator_factory

		self.__is_disposed = False
		self.__buffer = self.__buffer_factory.get_buffer()
		self.__waiting_for_buffer_queue = []
		self.__uuid_generator = self.__uuid_generator_factory.get_uuid_generator()
		self.__semaphore_request_queue = SemaphoreRequestQueue(
			acquired_semaphore_names=[]
		)
		self.__get_buffer_started_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[
					"buffer semaphore"
				],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__get_buffer_ended_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=[
					"buffer semaphore"
				],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__push_window_started_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[
					"buffer semaphore"
				],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__push_window_ended_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=[
					"buffer semaphore"
				],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__append_started_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[
					"buffer semaphore"
				],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__append_ended_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=[
					"buffer semaphore"
				],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__extend_started_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[
					"buffer semaphore"
				],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__extend_ended_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=[
					"buffer semaphore"
				],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__dispose_started_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[
					"buffer semaphore"
				],
				release_semaphore_names=[],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)
		self.__dispose_ended_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=[
					"buffer semaphore"
				],
				is_release_async=False
			),
			semaphore_request_queue=self.__semaphore_request_queue
		)

	def get_buffer(self) -> tuple:
		print("WindowBuffer: get_buffer: start")
		self.__get_buffer_started_prepared_semaphore_request.apply()
		_buffer = self.__buffer.get()
		self.__get_buffer_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: get_buffer: end")
		return _buffer

	def push_window(self, offset: int):
		print("WindowBuffer: push_window: start")
		self.__push_window_started_prepared_semaphore_request.apply()
		if self.__is_disposed:
			self.__push_window_ended_prepared_semaphore_request.apply()
			raise DisposedException()
		else:
			if self.__buffer.length() < offset:
				_local_semaphore_name = self.__uuid_generator.get_uuid()
				_remote_semaphore_name = self.__uuid_generator.get_uuid()
				_local_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_local_semaphore_name
						],
						release_semaphore_names=[],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_swap_local_and_remote_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_remote_semaphore_name
						],
						release_semaphore_names=[
							_local_semaphore_name
						],
						is_release_async=True
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_reserve_local_block_and_remote_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_local_semaphore_name,
							_remote_semaphore_name
						],
						release_semaphore_names=[
							"buffer semaphore"
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_remote_unblock_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_remote_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_cancel_local_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_local_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_local_and_remote_done_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_local_semaphore_name,
							_remote_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)

				_is_cancelled = False

				def _cancel_method():
					_is_cancelled = True
					_cancel_local_block_prepared_semaphore_request.apply()

				def _process_method():
					_swap_local_and_remote_prepared_semaphore_request.apply()

				def _done_method():
					_local_and_remote_done_prepared_semaphore_request.apply()

				self.__waiting_for_buffer_queue.append((offset, _process_method, _cancel_method, _done_method))
				_reserve_local_block_and_remote_block_prepared_semaphore_request.apply()
				_local_block_prepared_semaphore_request.apply()
				if not _is_cancelled:
					self.__buffer.push(offset)
				_remote_unblock_prepared_semaphore_request.apply()
				if _is_cancelled:
					raise CancelledException()
			else:
				self.__buffer.push(offset)
				self.__push_window_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: push_window: end")

	def get_window(self, length: int) -> tuple:
		print(f"WindowBuffer: get_window: start: {length}")
		_window = None
		self.__push_window_started_prepared_semaphore_request.apply()
		if self.__is_disposed:
			self.__push_window_ended_prepared_semaphore_request.apply()
			raise DisposedException()
		else:
			if self.__buffer.length() < length:
				_local_semaphore_name = self.__uuid_generator.get_uuid()
				_remote_semaphore_name = self.__uuid_generator.get_uuid()
				_local_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_local_semaphore_name
						],
						release_semaphore_names=[],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_swap_local_and_remote_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_remote_semaphore_name
						],
						release_semaphore_names=[
							_local_semaphore_name
						],
						is_release_async=True
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_reserve_local_block_and_remote_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[
							_local_semaphore_name,
							_remote_semaphore_name
						],
						release_semaphore_names=[
							"buffer semaphore"
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_remote_unblock_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_remote_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_cancel_local_block_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_local_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)
				_local_and_remote_done_prepared_semaphore_request = PreparedSemaphoreRequest(
					semaphore_request=SemaphoreRequest(
						acquire_semaphore_names=[],
						release_semaphore_names=[
							_local_semaphore_name,
							_remote_semaphore_name
						],
						is_release_async=False
					),
					semaphore_request_queue=self.__semaphore_request_queue
				)

				_is_cancelled = False

				def _cancel_method():
					_is_cancelled = True
					_cancel_local_block_prepared_semaphore_request.apply()

				def _process_method():
					_swap_local_and_remote_prepared_semaphore_request.apply()

				def _done_method():
					_local_and_remote_done_prepared_semaphore_request.apply()

				self.__waiting_for_buffer_queue.append((length, _process_method, _cancel_method, _done_method))
				_reserve_local_block_and_remote_block_prepared_semaphore_request.apply()
				_local_block_prepared_semaphore_request.apply()
				if not _is_cancelled:
					_window = self.__buffer.request(length)
				_remote_unblock_prepared_semaphore_request.apply()
				if _is_cancelled:
					raise CancelledException()
			else:
				_window = self.__buffer.request(length)
				self.__push_window_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: get_window: end")
		return _window

	def append(self, item):
		print("WindowBuffer: append: start")
		self.__append_started_prepared_semaphore_request.apply()
		if self.__is_disposed:
			self.__append_ended_prepared_semaphore_request.apply()
			raise DisposedException()
		else:
			print("WindowBuffer: append: self.__buffer.append(item)")
			self.__buffer.append(item)
			print(f"WindowBuffer: append: len(self.__waiting_for_buffer_queue) != 0: {len(self.__waiting_for_buffer_queue) != 0}")
			if len(self.__waiting_for_buffer_queue) != 0:
				print(f"WindowBuffer: append: self.__buffer.length() >= self.__waiting_for_buffer_queue[0][0]: {self.__buffer.length() >= self.__waiting_for_buffer_queue[0][0]}")
			while len(self.__waiting_for_buffer_queue) != 0 and self.__buffer.length() >= self.__waiting_for_buffer_queue[0][0]:
				_, _process_method, _, _done_method = self.__waiting_for_buffer_queue.pop(0)
				print(f"processing...")
				_process_method()
				print(f"done...")
				_done_method()
				print("loop over")
			self.__append_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: append: end")

	def extend(self, item):
		print("WindowBuffer: extend: start")
		self.__extend_started_prepared_semaphore_request.apply()
		if self.__is_disposed:
			self.__extend_ended_prepared_semaphore_request.apply()
			raise DisposedException()
		else:
			self.__buffer.extend(item)
			while len(self.__waiting_for_buffer_queue) != 0 and self.__buffer.length() >= self.__waiting_for_buffer_queue[0][0]:
				_, _process_method, _, _done_method = self.__waiting_for_buffer_queue.pop(0)
				_process_method()
				_done_method()
			self.__extend_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: extend: end")

	def dispose(self):
		print("WindowBuffer: dispose: start")
		self.__dispose_started_prepared_semaphore_request.apply()
		if self.__is_disposed:
			self.__dispose_ended_prepared_semaphore_request.apply()
			raise DisposedException()
		else:
			while len(self.__waiting_for_buffer_queue) != 0:
				_, _, _cancel_method, _done_method = self.__waiting_for_buffer_queue.pop(0)
				_cancel_method()
				_done_method()
			self.__is_disposed = True
			self.__dispose_ended_prepared_semaphore_request.apply()
		print("WindowBuffer: dispose: end")
