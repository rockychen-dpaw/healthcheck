from datetime import datetime

from . import utils

class CycleList:
    def __init__(self,maxlen):
        self._list = []
        if maxlen <= 0:
            raise Exception("Maximum length({}) must be greater than 0".format(maxlen))
        self._maxlen = maxlen 
        self._index = 0
        self._size = 0
        self._id = int(utils.now().timestamp())

    def add(self, item):
        if self._index < len(self._list):
            self._list[self._index] = item
        else:
            self._list.append(item)

        self._index += 1
        self._size += 1
        if self._index == self._maxlen:
            self._index = 0

    def __getitem__(self, index):
        return self._list[index]

    def __len__(self):
        with self._lock:
            return len(self._list)

    @property
    def totalsize(self):
        return self._size

    @property
    def index(self):
        return self._index

    @property
    def lastitem_index(self):
        """
        Return the index of last item if have; otherwise return -1 if no data in list

        """
        if self._index == 0:
            if self._list:
                return self._maxlen - 1
            else:
                return -1
        else:
            return self._index - 1


    class _ListReader(object):
        def __init__(self,list,index):
            self._list = list
            self._index = index

        def items(self):
            while self._index != self._list._index:
                yield self._list._list[self._index]
                self._index += 1
                if self._index == self._list._maxlen:
                    self._index = 0

        def is_compatible(self,listid,nextindex):
            return self._list._id == listid and (self._list.totalsize - nextindex) <= self._maxlen

    def get_reader(self,index = 0):
        if index >= 0:
            return self._ListReader(self,index)
        else:
            return self._ListReader(self,0)

