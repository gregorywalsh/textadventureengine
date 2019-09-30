from os import name as os_name
from engine import Game, Terminal, Player

SCENE_DAT_FP = 'adv_cangranaria.yaml'
PARSE_DAT_FP = 'parsing.yaml'

game = Game(
    game_data_fp=SCENE_DAT_FP,
    parsing_data_fp=PARSE_DAT_FP,
    printer=Terminal(width=50, os_name=os_name),
    player=Player(
        initial_scene=None,
        initial_inventory=set(),
        states=set(),
        visited_scene_names=set()
    )
)

game.start()
