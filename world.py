
from collections import defaultdict

from matplotlib.pylab import Enum
import numpy as np

from common import log, log_level

#region global variables
DIRS = {
    'W': (0, -1),
    'E': (0, 1),
    'N': (-1, 0),
    'S': (1, 0),
}
DIRS_INV = defaultdict(lambda : str('WAIT'))
for k,v in DIRS.items():
    DIRS_INV[v] = k
#region singal handling
#GAUS_RING_INTERVALS = [3.0, 2.5, 2.0, 1.5, 1.0]#, 0.75, 0.66, 0.5, 0.33, 0.25]
GAUS_RING_INTERVALS = [1.0, 0.75, 0.66, 0.5, 0.33, 0.25]
# GAUS_RING_INTERVALS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
SIGMA = 1.5
SIGNAL_MAP_DECAY = 0.9
SIGNAL_THRESHHOLD = 0.5
COPUTE_THREASHOLD = 0.75
NUM_SIGNAL_OCCOURENCES = 2
#endregion
MAX_PATROL_TARGET = 10
PLAN_GEMS = 'known_gems'
PLAN_COMPUTED = 'computed_gems'
PLAN_SIGNAL = 'potential_gems'
PLAN_UNKNOWN = 'exploration'
PLAN_OPPONENTS = 'opponents'
PLAN_PATROL = 'patrol'
PLAN_ANTENNA = 'antenna'
#endregion
#region quadrants
NW = 'North-West'
NE = 'North-East'
SW = 'South-West'
SE = 'South-East'
#endregion

class field_type(Enum):
    unknown = 10
    field = 1
    wall = 100

class World:
    def __init__(__self__):
        __self__.field = None
        __self__.width = -1
        __self__.heigth = -1
        __self__.world_changed = True
        __self__.bot_pos = None
        __self__.visible_fields:dict[tuple[int,int]:set[tuple[int,int]]] = {}#Dict for position to view other positions
        __self__.gems_seen = {}
        __self__.fields_seen = {}
        __self__.history = []
    def update_config(__self__,width:int,height:int):
        __self__.field = np.ones((height,width),dtype=np.int16)
        __self__.field *= field_type.unknown.value
        __self__.width = width
        __self__.height = height
        __self__.mid_width = width//2
        __self__.mid_height = height//2
        __self__.world_changed = True
        __self__.antenna_positions = {NW: (__self__.mid_height//2,__self__.mid_width//2),
                                      SE: ((3*__self__.mid_height)//2,(3*__self__.mid_width)//2),
                                      NE: (__self__.mid_height//2,(3*__self__.mid_width)//2),
                                      SW: ((3*__self__.mid_height)//2,__self__.mid_width//2)}
    def update_walls(__self__,data:list):
        value_before = np.sum(data)
        for wall in data:
            __self__.field[wall[1],wall[0]] = field_type.wall.value
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
            log('Changing world (new Walls).')
    def update_floor(__self__,data:list):
        value_before = np.sum(data)
        __self__.fields_seen ={k:v+1 for k,v in __self__.fields_seen.items()}
        for floor in data:
            __self__.field[floor[1],floor[0]] = field_type.field.value
            __self__.fields_seen[(floor[1],floor[0])] = 0
        value_after = np.sum(data)
        if value_after != value_before:
            __self__.world_changed = True
            log('Changing world (new Floor).')
        log(f'Floor update done, new count: {np.unique(__self__.field,return_counts=True)}')
        __self__.update_fields(__self__.bot_pos,data)
    def update_fields(__self__,current_pos:tuple[int,int],data:list):
        log(f'Number of new Data points: {len(data)}')
        if current_pos in __self__.visible_fields:
            return #No update necessary
        __self__.visible_fields[current_pos] = [(x[1],x[0]) for x in data]
    def update_gems(__self__,data:list):
        value_before = len(__self__.gems_seen)        
        for pos in __self__.visible_fields[__self__.bot_pos]:
            __self__.gems_seen.pop(pos,None)
        for gem in data:
            __self__.gems_seen[(gem['position'][1],gem['position'][0])] = gem['ttl']
        value_after = len(__self__.gems_seen)
        if value_before != value_after:
            __self__.world_changed = True
            log('Changing world (new Gems).')
        log(f'There are currently {len(__self__.gems_seen)} Gems in the list')
    def update_bot(__self__,data:dict):
        pos = data['bot']
        __self__.bot_pos = (pos[1],pos[0])
    def analyse_world(__self__,data:dict):
        __self__.world_changed = False
        __self__.history.append(data)
        __self__.update_bot(data)
        __self__.update_walls(data.get("wall",[]))
        __self__.update_floor(data.get("floor",[]))
        __self__.update_gems(data.get('visible_gems',[]))