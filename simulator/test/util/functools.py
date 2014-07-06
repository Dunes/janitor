'''
Created on 22 Jun 2014

@author: jack
'''

def as_list(function):
    return wrap(list, function)

def wrap(wrapper, wrapped, *args, **kwargs):
    def function(*args_, **kwargs_):
        return wrapper(wrapped(*args_, **kwargs_), *args, **kwargs)
    return function