#!/usr/bin/env python3
from astar_bot import signal_bot
from potential_field import gem_bot
if __name__ == "__main__":
    signal_bot().main()
    # gem_bot().main()
    # bot = gem_bot()
    # bot.width = 24
    # bot.height =12
    # bot.current_pos = (2,3)
    # bot.walls = np.ones((bot.height,bot.width),dtype=np.int8)
    # bot.walls[5,3] = 0
    # bot.walls[3,3] = 0
    # bot.walls[5,2] = 0
    # bot.walls[4,2] = 0
    # bot.use_signal = True
    # bot.signal_radius = 3
    # print(bot.analyse_signal2(0.75))
    # print(bot.build_field((4,4)))
    # print(bot.build_field((4,4),decay=None))
    # bot.anchor_views = {
    #     (2,3): {(1,1),(1,2),(2,1)},
    #     (5,5): {(4,4),(4,5),(5,4)},
    #     (1,5): {(0,4),(0,5),(1,4),(4,5),(7,1),(8,0)},
    #     (8,1): {(7,0),(7,1),(8,0)},
    #     (0,4): {(0,4),(0,5),(1,4)}
    # }
    # print(bot.create_achrons())
    # field = np.zeros((10,20),dtype=np.int8)
    # print(field)
    # print('----')
    # field[2,2] = field_type.wall.value
    # print(field)
    # ft =  field_type(field[2,2])
    # print(ft)
    # print([tuple(x) for x in np.argwhere(field >= field_type.wall.value)])
    w = World()
    w.update_config(20,10)
    w.field[3,2] = field_type.wall.value
    print(w.field)
    p = Planer(w)
    print(p.path_planing((2,2),(2,4)))