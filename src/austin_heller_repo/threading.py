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
		self.__added_ands = []
		self.__added_nands = []

	def get(self) -> bool:

		# AND - true until at least one false
		# value		br		outcome
		#	F		F			F
		#	F		T			F
		#	T		F			F
		#	T		T			T

		# NAND - false until at least one true
		# value		br		outcome
		#	F		F			F
		#	F		T			T
		#	T		F			T
		#	T		T			T

		value = self.__value
		for boolean_reference in self.__added_ands:
			value = value and boolean_reference.get()
		for boolean_reference in self.__added_nands:
			value = value != boolean_reference.get()
		return self.__value

	def set(self, value: bool):
		self.__value = value

	def add_and(self, boolean_reference):
		# true until one is false
		self.__added_ands.append(boolean_reference)
		if len(self.__added_nands) != 0:
			raise Exception("Cannot add both ands and nands.")

	def add_nand(self, boolean_reference):
		# false until one is true
		self.__added_nands.append(boolean_reference)
		if len(self.__added_ands) != 0:
			raise Exception("Cannot add both ands and nands.")

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

	def __init__(self, *, acquire_semaphore_names, release_semaphore_names):

		self.__acquire_semaphore_names = acquire_semaphore_names
		self.__release_semaphore_names = release_semaphore_names

	def get_aquire_semaphore_names(self):
		return self.__acquire_semaphore_names

	def get_release_semaphore_names(self):
		return self.__release_semaphore_names


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

		def _try_process_semaphore_request(*, semaphore_request: SemaphoreRequest) -> bool:
			# can this semaphore request acquire the necessary semaphores?
			_is_at_least_one_acquired_semaphore = False
			_is_at_least_one_released_semaphore = False
			for _acquire_semaphore_name in _semaphore_request.get_aquire_semaphore_names():
				if _acquire_semaphore_name in self.__acquired_semaphore_names:
					# this acquire semaphore name is already acquired, so it cannot be acquired again
					_is_at_least_one_acquired_semaphore = True
					break
			if not _is_at_least_one_acquired_semaphore:
				# can this semaphore request release the necessary semaphores?
				for _release_semaphore_name in _semaphore_request.get_release_semaphore_names():
					if _release_semaphore_name not in self.__acquired_semaphore_names:
						# this release semaphore name is not currently acquired, so it cannot be released
						_is_at_least_one_released_semaphore = True
						break

			if not _is_at_least_one_acquired_semaphore and not _is_at_least_one_released_semaphore:
				self.__acquired_semaphore_names.extend(_semaphore_request.get_aquire_semaphore_names())
				for _release_semaphore_name in _semaphore_request.get_release_semaphore_names():
					self.__acquired_semaphore_names.remove(_release_semaphore_name)
				return True
			return False

		self.__dequeue_semaphore.acquire()

		_is_queue_empty = False
		while not _is_queue_empty:

			# try to process first pending semaphore request

			self.__queue_semaphore.acquire()
			_semaphore_request, _blocking_semaphore = self.__active_queue.pop(0)
			_is_queue_empty = (len(self.__active_queue) == 0)
			self.__queue_semaphore.release()

			_is_active_semaphore_request_processed = _try_process_semaphore_request(
				semaphore_request=_semaphore_request
			)

			# if it could be processed, then release blocking semaphore and run through the pending semaphore requests
			if _is_active_semaphore_request_processed:
				_blocking_semaphore.release()
				#time.sleep(0.01)

				_is_pending_semaphore_request_processed = True
				while _is_pending_semaphore_request_processed and len(self.__pending_queue) != 0:
					for _pending_queue_index, (_semaphore_request, _blocking_semaphore) in enumerate(self.__pending_queue):
						_is_pending_semaphore_request_processed = _try_process_semaphore_request(
							semaphore_request=_semaphore_request
						)
						if _is_pending_semaphore_request_processed:
							_blocking_semaphore.release()
							del self.__pending_queue[_pending_queue_index]

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


class ReadOnlyAsyncHandle():

	def __init__(self, *, is_cancelled: BooleanReference):

		self.__is_cancelled = is_cancelled

	def is_cancelled(self) -> bool:
		return self.__is_cancelled.get()


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
		self.__result = self.__get_result_method(self)
		self.__is_storing = False
		self.__wait_for_result_semaphore.release()

	def __wait_for_result(self):

		self.__wait_for_result_semaphore.acquire()
		self.__wait_for_result_semaphore.release()

	def get_readonly_async_handle(self) -> ReadOnlyAsyncHandle:
		return ReadOnlyAsyncHandle(
			is_cancelled=self.__is_cancelled
		)

	def is_cancelled(self) -> bool:
		return self.__is_cancelled.get()

	def add_parent(self, async_handle):
		# this can be an AsyncHandle or ReadOnlyAsyncHandle
		self.__is_cancelled.add_nand(async_handle.__is_cancelled)

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
				release_semaphore_names=[]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__starting_try_cycle_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=["try cycle"],
				release_semaphore_names=[]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__finished_try_cycle_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__finished_try_cycle_and_unblock_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle", "blocking cycle"]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__try_get_next_work_queue_element_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=["try cycle"],
				release_semaphore_names=[]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__acknowledge_nonempty_work_queue_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"]
			),
			semaphore_request_queue=self.__cycle_semaphore_request_queue
		)
		self.__acknowledge_empty_work_queue_prepared_semaphore_request = PreparedSemaphoreRequest(
			semaphore_request=SemaphoreRequest(
				acquire_semaphore_names=[],
				release_semaphore_names=["try cycle"]
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