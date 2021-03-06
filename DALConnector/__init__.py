from __future__ import absolute_import, print_function, unicode_literals
from .DALConnector import DALConnector

def create_instance(c_instance):
    return DALConnector(c_instance = c_instance)

