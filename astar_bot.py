import json
import sys

from planer import Planer
from world import  World
from common import  log, log_level



#endregion



class signal_bot:
    def __init__(__self__):
        __self__.world = World()
        __self__.planer = Planer(__self__.world)
        __self__.first_tick = True
    def main(__self__):
        for line in sys.stdin:
            log('*'*30)
            data = json.loads(line)
            if __self__.first_tick:
                __self__.analyse_first_tick(data)
            __self__.world.analyse_world(data)
            __self__.planer.analyse(data)
            __self__.select_move()

    def analyse_first_tick(__self__,data):
        log('First Tick',log_level.INFO)
        __self__.first_tick = False
        __self__.world.update_config(width=data['config']['width'],height = data['config']['height'])
        __self__.planer.update()
        __self__.planer.signal_radius  = data['config']["signal_radius"]
        __self__.world.signal_radius = data['config']["signal_radius"]
        __self__.world.max_gems = data['config']["max_gems"]
        __self__.planer.max_antenna = data['config'].get("max_antennas",-1)
        __self__.planer.max_portals = data['config'].get("max_portals",-1)
        __self__.planer.set_antenna = 0
        __self__.planer.plan_antenna.target_antenna_num = min(2,__self__.planer.max_antenna) #really bad style
        log(f'Setting target antenna num to {__self__.planer.plan_antenna.target_antenna_num}')

    def select_move(__self__):
        move = __self__.planer.get_next_move()
        highlight = __self__.planer.highlight_targets()
        highlight = ' ' + json.dumps(highlight)
        message = f'{move}{highlight}' 
        print(message,flush=True)