import fcntl

class FileLock(object):
    def __init__(self,file):
        self.file = file
        self._fd = None

    def __enter__(self):
        if self._fd:
            raise Exception("Already acquired the lock({})".format(self.file))
        self._fd = open(self.file,'w')
        fcntl.flock(self._fd.fileno(),fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._fd:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            finally:
                try:
                    self._fd.close()
                except Exception as ex:
                    pass
                finally:
                    self._fd = None
        return False if exc_type else True

