class Future:
    
    def __init__(self):
        self._result = None
        self._exception = None
        self._done = False
        self._callbacks = []

    def set_result(self, result):
        self._result = result
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def set_exception(self, exception):
        self._exception = exception
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def done(self):
        return self._done

    def result(self):
        if self._exception:
            raise self._exception
        return self._result

    def add_done_callback(self, fn):
        if self._done:
            fn(self)
        else:
            self._callbacks.append(fn)

    def __iter__(self):
        yield self
        return self.result()

    def __await__(self):
        return self.__iter__() 