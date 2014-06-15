

class total_ordering(object):

	def __init__(self, key=None):
		self.key = key if key else id
	
	def __call__(self, cls):
		return self.decorator(cls)
	
	@staticmethod
	def eq(key):
		def __eq__(self, other):
			return key(self) == key(other)
		return __eq__
		
	@staticmethod
	def ne(key):
		def __ne__(self, other):
			return key(self) != key(other)
		return __ne__
		
	@staticmethod
	def lt(key):
		def __lt__(self, other):
			return key(self) < key(other)
		return __lt__
		
	@staticmethod
	def le(key):
		def __le__(self, other):
			return key(self) <= key(other)
		return __le__
		
	@staticmethod
	def gt(key):
		def __gt__(self, other):
			return key(self) > key(other)
		return __gt__
		
	@staticmethod
	def ge(key):
		def __ge__(self, other):
			return key(self) >= key(other)
		return __ge__

	def decorator(self, cls):
	
		if isinstance(self.key, basestring):
			self.key = getattr(cls, self.key)
			
		if isinstance(self.key, property):
			self.key = self.key.fget
		
		if not callable(self.key):
			raise ValueError("key is not callable or a valid property")
		
		cls.__eq__ = self.eq(self.key)
		cls.__ne__ = self.ne(self.key)
		cls.__lt__ = self.lt(self.key)
		cls.__le__ = self.le(self.key)
		cls.__gt__ = self.gt(self.key)
		cls.__ge__ = self.ge(self.key)
		
		return cls

