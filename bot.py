#!/usr/bin/env python3
import sys, json, random

random.seed(1)
def log(text:str):
    print(text,flush=True,file=sys.stderr)
def main():
    first_tick = True
    log('Dies ist ein Test')
    for line in sys.stdin:
        data = json.loads(line)
        if first_tick:
            config = data.get("config", {})
            width = config.get("width")
            height = config.get("height")
            log(f"Random walker (Python) launching on a {width}x{height} map")
        bot_pos = data.get("bot",[1,1])
        log(f'Bot Position: {bot_pos}')
        for gem in data.get('visible_gems',[]):
            log(f'  Gem at {gem.get("position","")}')
        if len(data["visible_gems"]) > 0:
            gem_pos = data['visible_gems'][0]['position']
            bot_x = bot_pos[0]
            gem_x = gem_pos[0]
            bot_y = bot_pos[1]
            gem_y = gem_pos[1]
            if gem_x > bot_x:
                move = 'E'
            elif gem_x < bot_x:
                move = 'W'
            elif gem_y > bot_y:
                move = 'S'
            elif gem_y < bot_y:
                move = 'N'
            else:
                move = random.choice(["N", "S", "E", "W"])
        else:
            move = random.choice(["N", "S", "E", "W"])
        print(move, flush=True)
        first_tick = False
if __name__ == '__main__':
    main()