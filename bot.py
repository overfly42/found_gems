#!/usr/bin/env python3
import sys, json, random
import itertools
import numpy as np
from uuid import uuid4


DEBUG = False
MAX_DISTANCE = 2
DECAY_FACTOR = 0.8
NUMBER_OF_LAST_POSITIONS = 10
OPPONENT_PENALTY_TTL = 5


random.seed(1)
class gem_searcher:
    def __init__(__self__):
        __self__.config = {}
        __self__.width = 0
        __self__.height = 0
        __self__.first_tick = True
        __self__.counter = 0
        __self__.current_tick = 0
        __self__.max_ticks = 0
        __self__.central_map = None
        __self__.last_positions = []
        __self__.folder = str(uuid4())
        __self__.walls = None
        __self__.gems = {}
        # __self__.fields = None
        __self__.known_fields = set()
        __self__.known_walls = set()
        __self__.visible_fields = []
        __self__.next_corner = None
        __self__.corners = None
        __self__.corner_index = 0
        # __self__.unseen_pos = None
        __self__.target_pos = 0
        __self__.current_target = None
        __self__.target_not_reached_counter = 10
        __self__.visited_targets = set()
        if DEBUG:
            import os
            os.makedirs(__self__.folder,exist_ok=True)
    def main(__self__):
        for line in sys.stdin:
            __self__.log('----------------')
            data = json.loads(line)

            __self__.analyse_json(data)
            map = __self__.build_map()
            move = __self__.select_move(map)
            print(move, flush=True)

    def log(__self__,message):
        '''Writes to STD ERR if DEBUG is enabled'''
        if DEBUG:
            print(message,file=sys.stderr,flush=True)
    def store(__self__,value,prefix:str='data'):
        '''Stores the bot state to a file if DEBUG is enabled. Each file is numbered sequentially'''
        __self__.counter += 1
        if DEBUG:
            with open(f"{__self__.folder}/{prefix}_bot_state{__self__.counter:05}.json","w") as f:
                json.dump(value,f)

    def calc_distance(__self__,pos1:tuple[int,int],pos2:tuple[int,int])->int:
        '''
            Simple helper function to calulate Manhattan distance
        '''
        return abs(pos1[0]-pos2[0]) + abs(pos1[1]-pos2[1])

    def analyse_json(__self__,data):
        __self__.store(data,'raw')
        if __self__.first_tick:
            __self__.log('First Tick')
            __self__.config = data.get("config", {})
            __self__.width = __self__.config.get("width")
            __self__.height = __self__.config.get("height")
            __self__.max_ticks = __self__.config.get("max_ticks")
            __self__.first_tick = False
            __self__.walls = np.ones((__self__.height,__self__.width))
            # __self__.fields = np.ones((__self__.height,__self__.width))
            __self__.central_map = __self__.build_single_map({'x_gem':__self__.width//2,'y_gem':__self__.height//2,'ttl':MAX_DISTANCE})
            __self__.corners = [ (1,1), (1,__self__.height-2), (__self__.width-2,1), (__self__.width-2,__self__.height-2) ]
        __self__.current_tick = data.get("tick")
        __self__.opponents = [x['position'] for x in data.get("visible_bots",[])]
        my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
        __self__.last_positions.append(my_pos['bot'])
        __self__.visited_targets.add((my_pos['bot'][0],my_pos['bot'][1]))
        for wall in data.get('wall'):
            __self__.walls[wall[1],wall[0]] = 0
            __self__.known_walls.add((wall[0],wall[1]))
        # for tile in data.get('floor'):
        #     __self__.fields[tile[1],tile[0]] = 0.5
        __self__.visible_fields = {(x[0],x[1]) for x in data.get('floor')}
        __self__.known_fields.update(__self__.visible_fields)
        if __self__.current_tick % 50 == 0 or __self__.next_corner in data.get('wall') or __self__.next_corner in data.get('floor'):
            __self__.corner_index += 1
        # __self__.unseen_pos = []
        # for x,y in itertools.product(range(__self__.width),range(__self__.height)):
        #     if __self__.walls[y,x] > 0.8 and __self__.fields[y,x] > 0.8:
        #         __self__.unseen_pos.append( {'x_gem':x,'y_gem':y,'ttl':5} )
        if len(__self__.last_positions) > NUMBER_OF_LAST_POSITIONS:
            __self__.last_positions.pop(0)
        for gem in __self__.gems.values():
            gem['ttl'] -= 1
        outdated_gems = [key for key,gem in __self__.gems.items() if gem['ttl'] <= 0]
        outdated_gems.extend([key for key,gem in __self__.gems.items() if gem['x_gem'] == my_pos['bot'][0] and gem['y_gem'] == my_pos['bot'][1]])
        for key in outdated_gems:
            __self__.gems.pop(key)
        for gem in my_pos["visible_gems"]:
            __self__.gems[(gem['position'][0],gem['position'][1])] = {
            'x_gem': gem['position'][0],
            'y_gem': gem['position'][1],
            'ttl': gem['ttl'],
            'distance_to_oppeent': min([__self__.calc_distance(gem['position'],opp) for opp in __self__.opponents]) if __self__.opponents else float('inf'),
            'distance':__self__.calc_distance(my_pos['bot'], gem['position'])
            }
        __self__.my_pos = my_pos

    # New Logic using overlayed maps
    def build_single_map(__self__,gem):
        '''
            Build a distance decay map for a single gem. Most victory_points are near the gem, decaying with manhatten distance
        '''
        x0 = gem['x_gem']
        y0 = gem['y_gem']
        x = np.arange(__self__.width)
        y = np.arange(__self__.height)[:,None]
        distance = gem['ttl'] * DECAY_FACTOR**( np.abs(x - x0) + np.abs(y - y0))
        return distance
    def build_map(__self__,)->np.ndarray:
        '''
            Build a distance decay map for all gems
        '''
        full_map = np.ones((__self__.height,__self__.width))
        # Remove Gems much closer to the opponent than to us
        orderd_gems = sorted(__self__.gems.values(),key=lambda x:x['distance_to_oppeent'] - x['distance'])
        do_remove = len(__self__.opponents) > 0
        enough_gems = len(orderd_gems) > 1
        removal_distance = enough_gems and ((orderd_gems[0]['distance_to_oppeent'] - orderd_gems[0]['distance']) > MAX_DISTANCE)
        if  do_remove and enough_gems and removal_distance:
            __self__.log(f'Removed gem at {orderd_gems[0]["x_gem"]},{orderd_gems[0]["y_gem"]} as too close to opponent')
            orderd_gems.pop(0)
        # Build a map for each gem and add it to the full map
        # if not orderd_gems:
        #     full_map += __self__.central_map
        # for gem in __self__.unseen_pos:
        #     single_map = __self__.build_single_map(gem)
        #     full_map += single_map * 0.01
        __self__.log(f'Building map with {len(orderd_gems)} gems')
        for gem in orderd_gems:
            single_map = __self__.build_single_map(gem)
            full_map += single_map*10
        for opp in __self__.opponents:
            single_map = __self__.build_single_map({'x_gem':opp[0],'y_gem':opp[1],'ttl':OPPONENT_PENALTY_TTL})
            full_map -= single_map
        if not __self__.gems:
            __self__.log(f'No visible gems. Current Target: {__self__.current_target}')
            __self__.target_not_reached_counter -= 1
            times_up = __self__.target_not_reached_counter <= 0
            target_reached = not __self__.current_target or (__self__.my_pos['bot'][0] == __self__.current_target[0] and __self__.my_pos['bot'][1] == __self__.current_target[1])
            __self__.log(f'Target not reached counter: {__self__.target_not_reached_counter}, times_up: {times_up}, target_reached: {target_reached}')
            if times_up or target_reached:
                current_target_list = sorted(__self__.known_fields.difference(__self__.visible_fields))
                reduced_targets = sorted(set(current_target_list).difference(__self__.visited_targets))
                if reduced_targets:
                    current_target_list = reduced_targets
                __self__.log(f'visited targets: {__self__.visited_targets}, remaining targets: {current_target_list}')
                __self__.target_pos += 1
                __self__.target_not_reached_counter = 10
                if current_target_list:
                    __self__.current_target = current_target_list[__self__.target_pos % len(current_target_list)]
                    __self__.visited_targets.add(__self__.current_target)
                else:
                    __self__.current_target = None
            if __self__.current_target:
                __self__.log(f'Moving to unseen field at {__self__.current_target}')
                target_map = __self__.build_single_map({'x_gem':__self__.current_target[0],'y_gem':__self__.current_target[1],'ttl':10})
                full_map += target_map
            else:
                __self__.log('No unseen fields')
                current_corner = __self__.corners[__self__.corner_index % len(__self__.corners)]           
                corner_map = __self__.build_single_map({'x_gem':current_corner[0],'y_gem':current_corner[1],'ttl':1})
                full_map += corner_map
            # unseen_fields = __self__.known_fields.difference(__self__.visible_fields)
            # for field in unseen_fields:
            #     single_map = __self__.build_single_map({'x_gem':field[0],'y_gem':field[1],'ttl':1})
            #     full_map += single_map
            # if not unseen_fields:
            #     __self__.log('No unseen fields')
            #     current_corner = __self__.corners[__self__.corner_index % len(__self__.corners)]           
            #     corner_map = __self__.build_single_map({'x_gem':current_corner[0],'y_gem':current_corner[1],'ttl':1})
            #     full_map += corner_map
            #Find all known but not currently visible fields
        # Set bot position to very low value to avoid selecting it
        # full_map[__self__.my_pos['bot'][1],__self__.my_pos['bot'][0]] = -0
        #Set all old positions to 0, to avoid going in circles
        for pos in __self__.last_positions:
            full_map[pos[1],pos[0]] = 0
        # Mask walls
        # full_map = full_map * 100
        # for wall in __self__.known_walls:
        #     wall_map = __self__.build_single_map({'x_gem':wall[0],'y_gem':wall[1],'ttl':0.01})
        #     full_map -= wall_map
        full_map = full_map * __self__.walls
        # for wall in __self__.known_walls:
        #     full_map[wall[1],wall[0]] = 0
        # # Set floor
        # full_map = full_map * __self__.fields
        return full_map
    def select_move(__self__,map:np.ndarray)->str:
        '''
            gathers the four values around the bot, and its values. selects the field with the highest value as next move
        '''
        # __self__.store({'map':str(map),'walls':str(__self__.walls),'fields':str(__self__.fields),'unseen':__self__.unseen_pos},'map')
        # __self__.store({'map':str(map),'walls':str(__self__.walls),'fields':str(__self__.fields)},'map')
        bot_x = __self__.my_pos['bot'][0]
        bot_y = __self__.my_pos['bot'][1]
        directions = {}
        #Map is indexed [y,x] Select the possible next steps
        directions['W']=map[bot_y,max(bot_x-1,0)]
        directions['E']=map[bot_y,min(bot_x+1,__self__.width-1)]
        directions['N']=map[max(bot_y-1,0),bot_x]
        directions['S']=map[min(bot_y+1,__self__.height),bot_x]
        __self__.log(f'Bot position: {bot_x},{bot_y} {directions}')    
        # if __self__.gems:
            # best_dir = max({v:k for k,v in directions.items()}.keys(),key=lambda x:np.sum(x))
            # return directions[best_dir]
            # __self__.last_move = None
        return max(directions,key=directions.get)
        # return 'WAIT'
#        directions = {v:k for k,v in directions.items()}
        # if __self__.last_move and directions[__self__.last_move] > 0.1:
        #     return __self__.last_move
        # if 'N' in directions and directions['N'] > 0.1:
        #     return 'N'
        # if 'E' in directions and directions['E'] > 0.1:
        #     return 'E'
        # if 'S' in directions and directions['S'] > 0.1:
        #     return 'S'
        # return 'W'

if __name__ == "__main__":
    gem_searcher().main()
