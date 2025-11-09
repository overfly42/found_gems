#!/usr/bin/env python3
import sys, json, random
import itertools

DEBUG = False
MAX_DISTANCE = 10
MAX_GEM_FOR_PERMUTATION = 7
#14289
# PS C:\Users\cspre\hidden-gems> ruby .\runner.rb -s 17eqmwy ..\found_gems\    

random.seed(1)
class gem_searcher:
    def __init__(__self__):
        __self__.config = {}
        __self__.width = 0
        __self__.height = 0
        __self__.first_tick = True
        __self__.counter = 0
        __self__.rect_path = None
    def calc_distance(__self__,pos1:tuple[int,int],pos2:tuple[int,int])->int:
        return abs(pos1[0]-pos2[0]) + abs(pos1[1]-pos2[1])
    def log(__self__,message):
        if DEBUG:
            print(message,file=sys.stderr,flush=True)

    def store(__self__,value):
        __self__.counter += 1
        if DEBUG:
            with open(f"bot_state{__self__.counter:05}.json","w") as f:
                json.dump(value,f)
    def analyse_json(__self__,data):
        __self__.store(data)
        if __self__.first_tick:
            __self__.log('First Tick')
            __self__.config = data.get("config", {})
            __self__.width = __self__.config.get("width")
            __self__.height = __self__.config.get("height")
            print(f"Overflys bot searching for gems on a {__self__.width}x{__self__.height} map",
                file=sys.stderr, flush=True)
            #__self__.rect_path = __self__.calc_rectangle(__self__.width,__self__.height)
            __self__.first_tick = False
        else:
            __self__.log('Subsequent Tick')
        my_pos = {'bot':data['bot'],"visible_gems":data.get("visible_gems",None)}
        if not my_pos["visible_gems"]:
            #pos = __self__.rect_path[__self__.counter % len(__self__.rect_path)]
            pos = (__self__.width //2, __self__.height //2)
            my_pos["visible_gems"] = [
                {'position':[pos[0],pos[1]],
                'ttl':1}
            ]
        gems = [{
        'x_gem':  x['position'][0],
        'y_gem': x['position'][1],
        'ttl': x['ttl'] - (abs(x['position'][0]-my_pos['bot'][0]) + abs(x['position'][1]-my_pos['bot'][1]))
        } for x in my_pos["visible_gems"]
        ]
        x_bot = my_pos["bot"][0]
        y_bot = my_pos["bot"][1]
        for x in gems:
            x['distance'] =  __self__.calc_distance(my_pos['bot'], (x['x_gem'],x['y_gem']))
        __self__.my_pos = my_pos
        return {'x':x_bot,'y':y_bot}, gems,my_pos
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
        __self__.log(f"Calculating permutations for {len(gems)} gems")
        for perm in itertools.permutations(gems):
            dist = perm[0]['distance']
            for i in range(len(perm)-1):
                dist += __self__.calc_distance((perm[i]['x_gem'],perm[i]['y_gem']), (perm[i+1]['x_gem'],perm[i+1]['y_gem']))
            if dist < best_dist:
                best_dist = dist
                best_order = perm
        return best_order[0]['x_gem'], best_order[0]['y_gem']
    def main(__self__):
        for line in sys.stdin:
            data = json.loads(line)

            bot, gems, meta_data = __self__.analyse_json(data)
            x_gem, y_gem = __self__.select_gem(gems) 

            if x_gem != bot['x']:
                move = 'E' if x_gem > bot['x'] else 'W'
            elif y_gem != bot['y']:
                move = 'S' if y_gem > bot['y'] else 'N'
            else:
                move = random.choice(["N", "S", "E", "W"])

            print(move, flush=True)
            meta_data['selected'] = move
            __self__.log(json.dumps(meta_data))
    def calc_rectangle(__self__,width:int,height:int)->list[tuple[int,int]]:
        rect = []
        w_start = width // 3
        w_end = width - w_start
        h_start = height // 3
        h_end = height - h_start
        for x in range(w_start,w_end):
            rect.append((x,h_start))
        for y in range(h_start,h_end):
            rect.append((w_end,y))
        for x in range(w_end,w_start-1,-1):
            rect.append((x,h_end))
        for y in range(h_end-1,h_start,-1):
            rect.append((w_start,y))
        return rect
if __name__ == "__main__":
    gem_searcher().main()