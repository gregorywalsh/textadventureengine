from skeleng import Game, Printer, Player

SCENE_DAT_FP = 'adv_cangranaria.yaml'
PARSE_DAT_FP = 'parsing.yaml'

game = Game(
    game_data_fp=SCENE_DAT_FP,
    parsing_data_fp=PARSE_DAT_FP,
    printer=Printer(width=80),
    player=Player(
        initial_scene=None,
        initial_inventory=set(),
        states=set(),
        visited_scene_names=set()
    )
)

game.start()
