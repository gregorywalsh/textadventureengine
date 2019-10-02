from os import name as os_name
from engine import Game, Shell, Player, InputParser

SCENE_DAT_FP = 'adv_cangranaria.yaml'
PARSE_DAT_FP = 'parsing.yaml'

game = Game(
    game_data_fp=SCENE_DAT_FP,
    input_parser=InputParser.construct_from_yaml(PARSE_DAT_FP),
    shell=Shell(width=65),
    player=Player(
        initial_scene=None,
        initial_inventory=set(),
        states=set(),
        visited_scene_names=set()
    )
)

game.start()
