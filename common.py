from enum import Enum
import sys

import numpy as np

class log_level(Enum):
    DEBUG = 1
    INFO = 2
    WARNING =3
    ERROR =4
    DEVELOP = 5
    GAME =6

LOG_LEVEL = log_level.INFO
#region Static tools
def log(message:str,log_level_value:log_level=log_level.INFO):
    '''
        Logs a message to stderr with the given log level
    '''
    if log_level_value.value >= LOG_LEVEL.value:
        print(f'[{log_level_value.name}] {message}',file=sys.stderr,flush=True)

def euclidian_distance(pos_a:tuple[int,int],pos_b:tuple[int,int])->float:
    return np.sqrt((pos_a[0]-pos_b[0])**2+(pos_a[1]-pos_b[1])**2)
