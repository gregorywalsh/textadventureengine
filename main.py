from classes import Game, Scene, Screen, Player

SCENE_DAT_FP = 'scenes.yaml'
PARSE_DAT_FP = 'parsing.yaml'

screen = Screen(width=80)
player = Player(
            initial_scene=None,
            initial_inventory=set(),
            visited_scene_names=set()
)

game = Game(
    scene_data_fp=SCENE_DAT_FP,
    parsing_data_fp=PARSE_DAT_FP,
    screen=screen,
    player=player
)

screen.print(
    paragraphs=['', 'Welcome to', '', '', 'CAN GRANARIA, AN ISLAND ADVENTURE!', '', ''],
    alignment='centre',
    clear=True
)
screen.print(
    paragraphs=["To play the game, enter simple commands such as 'look', 'go north' or 'give apple to man'", ''],
    alignment='left',
    clear=False
)
input('\tPress "ENTER" to continue: ')
screen.print(
    paragraphs=[],
    alignment='left',
    clear=True
)
game.start(scene='beach_lying')
