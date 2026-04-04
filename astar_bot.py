import json
import sys
import random
import os
import numpy as np

from enum import Enum
from collections import defaultdict, deque
from itertools import permutations

from planer import Planer
from world import DIRS, DIRS_INV, PLAN_COMPUTED, PLAN_UNKNOWN, World
from common import LOG_LEVEL, log, log_level

random.seed(1)


#endregion



class signal_bot:
    def __init__(__self__):
        __self__.world = World()
        __self__.planer = Planer(__self__.world)
        __self__.first_tick = True
    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line)
            __self__.planer.new_tick()
            __self__.analyse(data)
            __self__.planer.plan_global()
            __self__.select_move()
    def analyse(__self__,data:dict):
        # with open('file.json','w') as f:
        #     json.dump(data,f)
        __self__.world.history.append(data)
        __self__.world.world_changed = False
        if __self__.first_tick:
            __self__.analyse_first_tick(data)
        __self__.analyse_bot(data)
        __self__.world.update_walls(data.get("wall",[]))
        __self__.world.update_floor(data.get("floor",[]))
        __self__.world.update_gems(data.get('visible_gems',[]))

        if 'signal_level' in data:
            __self__.planer.analyse_global_signal(data.get('signal_level', 0.0))
        if 'channels' in data:
            __self__.planer.analyse_channel_signal(data.get('channels', []))
        elif 'antenna_signals' in data:
            __self__.planer.analyse_antenna_signal(data.get('antenna_signals', []))
    def analyse_first_tick(__self__,data):
        log('First Tick',log_level.DEBUG)
        __self__.first_tick = False
        __self__.world.update_config(width=data['config']['width'],height = data['config']['height'])
        __self__.planer.signal_radius  = data['config']["signal_radius"]
        __self__.planer.max_antenna = data['config'].get("max_antennas",-1)
        __self__.planer.set_antenna = 0
        __self__.planer.target_antenna_num = min(2,__self__.planer.max_antenna) 
        log(f'Setting target antenna num to {__self__.planer.target_antenna_num}')
    def analyse_bot(__self__,data):
        pos = data['bot']
        __self__.world.bot_pos = (pos[1],pos[0])
    def highlight_targets(__self__)->str:
        if LOG_LEVEL == log_level.GAME:
            return ''
        maps = {}
        highlight = []
        if PLAN_UNKNOWN in __self__.planer.targets and __self__.planer.targets[PLAN_UNKNOWN]:
            for pos in __self__.planer.targets[PLAN_UNKNOWN]:
                highlight.append([int(pos[1]),int(pos[0]),'#FFFFFF'])
        for pos in __self__.planer.current_path:
            highlight.append([int(pos[1]),int(pos[0]),'#F00000'])
        if PLAN_COMPUTED in __self__.planer.targets and __self__.planer.targets[PLAN_COMPUTED]:
            for pos in __self__.planer.targets[PLAN_COMPUTED]:
                highlight.append([int(pos[1]),int(pos[0]),'#00FF00'])
            y,x = __self__.planer.targets[PLAN_COMPUTED][0]
            highlight.append([int(x),int(y),'#991199'])
        maps['highlight'] = highlight
        return ' ' + json.dumps(maps)
    def select_move(__self__):
        if __self__.planer.next_antenna != None and len(__self__.planer.current_path) == 1:
            log(f'Moving towards antenna {__self__.planer.next_antenna} at position {__self__.world.antenna_positions[__self__.planer.next_antenna]}')
            direction = (np.sign(__self__.world.antenna_positions[__self__.planer.next_antenna][0]-__self__.world.bot_pos[0]),np.sign(__self__.world.antenna_positions[__self__.planer.next_antenna][1]-__self__.world.bot_pos[1]))
            log(f'selected direction: {direction}')
            move = f'PA{DIRS_INV[direction]}'
            bp = __self__.world.bot_pos 
            if move != 'PAWAIT':
                __self__.planer.antenna_placed[__self__.planer.next_antenna] += 1
                nd = DIRS[DIRS_INV[direction]]
                xxx = (bp[0]+nd[0],bp[1]+nd[1])
                __self__.world.fields_seen.pop(xxx,None)
                log(f'bot will move to {xxx}')
            __self__.planer.next_antenna = None
        elif __self__.planer.current_path:
            log(f'Path length: {len(__self__.planer.current_path)}')
            next_pos = __self__.planer.current_path[0]
            del __self__.planer.current_path[0]
            log(f'next_pos: {next_pos}')
            log(f'bot_pos: {__self__.world.bot_pos}')
            direction =(next_pos[0]-__self__.world.bot_pos[0],next_pos[1]-__self__.world.bot_pos[1])
            log(f'selected direction: {direction}')
            move = DIRS_INV[direction]
        else:
            move = random.choice(list(DIRS.keys()))
            __self__.planer.current_path.clear()
        if move == 'WAIT':
            __self__.planer.current_path.clear()
        print(f'{move}{__self__.highlight_targets()}',flush=True)