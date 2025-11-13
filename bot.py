#!/usr/bin/env python3
import sys, json, random
import itertools
import numpy as np


DEBUG = False
MAX_DISTANCE = 10
MAX_GEM_FOR_PERMUTATION = 8
DECAY_FACTOR = 0.7
USE_MAP_MOVE_SELECTOR = True
NUMBER_OF_LAST_POSITIONS = 3

#1you3km 
# Map Selector 9065
# Old Selector  14228

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
        __self__.central_pos = (0,0)
        __self__.last_positions = []
    def main(__self__):
        for line in sys.stdin:
            __self__.log('----------------')
            data = json.loads(line)

            bot, gems, meta_data = __self__.analyse_json(data)
            if USE_MAP_MOVE_SELECTOR:
                map = __self__.build_map(gems)
                move = __self__.select_move(map)
            else:
                move = None
            if not move:
                move = __self__.select_move_old(bot,gems)

            print(move, flush=True)
            meta_data['selected'] = move
            __self__.log(json.dumps(meta_data))
    def log(__self__,message):
        '''Writes to STD ERR if DEBUG is enabled'''
        if DEBUG:
            print(message,file=sys.stderr,flush=True)
    def store(__self__,value):
        '''Stores the bot state to a file if DEBUG is enabled. Each file is numbered sequentially'''
        __self__.counter += 1
        if DEBUG:
            with open(f"bot_state{__self__.counter:05}.json","w") as f:
                json.dump(value,f)

    def calc_distance(__self__,pos1:tuple[int,int],pos2:tuple[int,int])->int:
        '''
            Simple helper function to calulate Manhattan distance
        '''
        return abs(pos1[0]-pos2[0]) + abs(pos1[1]-pos2[1])

    def analyse_json(__self__,data):
        __self__.store(data)
        if __self__.first_tick:
            __self__.log('First Tick')
            __self__.config = data.get("config", {})
            __self__.width = __self__.config.get("width")
            __self__.height = __self__.config.get("height")
            __self__.central_pos = (__self__.width //2, __self__.height //2)
            __self__.max_ticks = __self__.config.get("max_ticks")
            __self__.first_tick = False
            #Say hello World
            print(f"Overflys bot searching for gems on a {__self__.width}x{__self__.height} map",file=sys.stderr, flush=True)
        __self__.current_tick = data.get("tick")
        my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
        __self__.last_positions.append(my_pos['bot'])
        if len(__self__.last_positions) > NUMBER_OF_LAST_POSITIONS:
            __self__.last_positions.pop(0)
        if not my_pos["visible_gems"]:
            my_pos["visible_gems"] = [
                {
                    'position':__self__.central_pos,
                    'ttl':1
                }
            ]
        gems = [{
            'x_gem':  x['position'][0],
            'y_gem': x['position'][1],
            'ttl': x['ttl']
            } for x in my_pos["visible_gems"]
        ]
        for x in gems:
            x['distance'] =  __self__.calc_distance(my_pos['bot'], (x['x_gem'],x['y_gem']))
        __self__.my_pos = my_pos
        return {'x':my_pos["bot"][0],'y':my_pos["bot"][1]}, gems,my_pos

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
    def build_map(__self__,gems:list[dict])->np.ndarray:
        '''
            Build a distance decay map for all gems
        '''
        full_map = np.zeros((__self__.height,__self__.width))
        # Build a map for each gem and add it to the full map
        for gem in gems:
            single_map = __self__.build_single_map(gem)
            full_map += single_map
        # Set bot position to very low value to avoid selecting it
        full_map[__self__.my_pos['bot'][1],__self__.my_pos['bot'][0]] = -0
        #Set all old positions to 0, to avoid going in circles
        for pos in __self__.last_positions:
            full_map[pos[1],pos[0]] = 0
        return full_map
    def select_move(__self__,map:np.ndarray)->str:
        '''
            gathers the four values around the bot, and its values. selects the field with the highest value as next move
        '''
        bot_x = __self__.my_pos['bot'][0]
        bot_y = __self__.my_pos['bot'][1]
        directions = {}
        #Map is indexed [y,x]
        directions[map[bot_y,max(bot_x-1,0)]] = 'W'
        directions[map[bot_y,min(bot_x+1,__self__.width-1)]] = 'E'
        directions[map[max(bot_y-1,0),bot_x]] = 'N'
        directions[map[min(bot_y+1,__self__.height),bot_x]] = 'S'
        __self__.log(f'Bot position: {bot_x},{bot_y} {directions}')
        if len(directions) <= 2:
            return None
        best_dir = max(directions.keys(),key=lambda x:np.sum(x))
        return directions[best_dir]

    # Old logic / fallback with o(x2) permutations
    def select_gem(__self__,gems) -> tuple[int,int]:
        if len(gems) > MAX_GEM_FOR_PERMUTATION:
            # Sort GEMS by distance and by points. Select the one with most points. If there is 
            dist_sort = sorted(gems,key=lambda x:x['distance'])
            point_sort = sorted(gems,key=lambda x:x['ttl'],reverse=True)
            if dist_sort[0]['distance'] <= MAX_DISTANCE:
                return dist_sort[0]['x_gem'], dist_sort[0]['y_gem']
            return point_sort[0]['x_gem'], point_sort[0]['y_gem']
        best_order = None
        best_dist = float('inf')
        best_points = -1000
        __self__.log(f"Calculating permutations for {len(gems)} gems")
        for perm in itertools.permutations(gems):
            dist = perm[0]['distance']
            points = perm[0]['ttl'] - dist
            for i in range(len(perm)-1):
                dist += __self__.calc_distance((perm[i]['x_gem'],perm[i]['y_gem']), (perm[i+1]['x_gem'],perm[i+1]['y_gem']))
                gem_catchable = dist <= perm[i+1]['ttl']
                gem_reachable = dist  + 1 <= __self__.max_ticks - __self__.current_tick
                if gem_reachable and gem_catchable:#Magic number to allow walk to the last tick.
                    points += perm[i+1]['ttl'] - dist
            if points > best_points or (points == best_points and dist < best_dist):
                best_points = points
                best_dist = dist
                best_order = perm
        return best_order[0]['x_gem'], best_order[0]['y_gem']
    def select_move_old(__self__,bot,gems)->str:
        __self__.log('Using old move selector')
        x_gem, y_gem = __self__.select_gem(gems) 

        if y_gem != bot['y']:
            move = 'S' if y_gem > bot['y'] else 'N'
        elif x_gem != bot['x']:
            move = 'E' if x_gem > bot['x'] else 'W'

        else:
            move = 'WAIT'#random.choice(["N", "S", "E", "W"])
        return move

if __name__ == "__main__":
    gem_searcher().main()
