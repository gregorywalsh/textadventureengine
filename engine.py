# Created by Gregory Walsh

"""
This module contains the necessary classes required to run a YAML Adventure File (YAF)
and an associated Input Parsing File (IPF).
"""

import os
import yaml
from pickle import dump
from textwrap import wrap, fill, indent

OS_NAME = os.name
if os.name == 'nt':
    import msvcrt


class Game:
    """
    Use this class to run a new game from an Adventure File (SAF).

    Args:
        game_data_fp (str): file path to a SAF
        input_parser (InputParser): an InputParser object for parsing Player inputs
        shell (Shell): a Shell for displaying the game and getting inputs
        player (Player): a Player object with state info such as inventory, location, etc.

    Attributes:
        player(Player): The Player of the game
        shell(Shell): The Game's shell. Can be used to print messages
    """

    def __init__(self, game_data_fp, input_parser, shell, player):
        self.player = player
        self.shell = shell
        self._metadata, self.scenes = Game._load_game_data(game_data_fp)
        self._input_parser = input_parser
        self._in_progress = True

    def start(self):
        """
        Initialises the Game by printing the title screen and beginning the input/action loop

        Returns:
            None
        """
        self.shell.clear()
        self.shell.print(
            paragraphs=['Welcome to', self._metadata['title']],
            alignment='centre'
        )
        self.shell.print(
            paragraphs=['To play the game, enter simple commands such as "look", "go north" or "give apple to man".'],
            alignment='left'
        )
        self.shell.pause()
        self.shell.clear()
        self.player.current_scene = self.scenes[self._metadata['first_scene']]
        self._play(self._metadata['first_action'])
        while self._in_progress:
            self._play()

    def _play(self, override_input=None):
        """ Performs a single game loop:
            request input -> find matching Action -> determine Outcome and execute associated Mutators
        """
        text_input = override_input if override_input else self.shell.get_player_input()
        action_key = self._input_parser.generate_action_key(text_input=text_input)
        action = self._match_action(action_key=action_key)
        outcome = self._match_outcome(action)
        if outcome:
            self._process_outcome(outcome)
        else:
            self.shell.print(
                paragraphs=['You cannot do that now.'],
                alignment='left'
            )

    def _match_action(self, action_key):
        """ Given an input, returns the first matching Action. Falls back to a default if there is one."""
        deault_action = None
        for action in self.player.current_scene.actions:
            if action.key_set == {'_no_match'}:  # Check for a default override
                deault_action = action
            if action.key_set == action_key:
                return action
        return deault_action

    def _match_outcome(self, action):
        """ Given an Action, returns the first possible matching Outcome by checking requirements against
            the Player's state.
            Examples:
                1. Player WITHOUT 'knife' attempts cut 'rope' by inputting "cut rope". The outcome may
                   be that the rope remains intact, and a msg saying so could be displayed.
                2. Player WITH 'knife' attempts cut 'rope' by inputting "cut rope". The outcome may
                   be that the rope is cut and placed in their inventory. A msg saying so could also be displayed.
        """
        matched_outcomes = [outcome for outcome in action.outcomes if outcome.check_reqs(self)]
        return matched_outcomes[0] if matched_outcomes else None

    def _process_outcome(self, outcome):
        """Processes outcome, e.g. change player location, and updates shell"""
        if outcome.clear:
            self.shell.clear()
        self.shell.print(
            paragraphs=outcome.text,
            alignment='left'
        )
        self._update_states(outcome)

    def _update_states(self, outcome):
        """Given an outcome, modifies player states e.g. location, inventory."""
        for state_mutator in outcome.mutators:
            state_mutator.mutator_func(self)

    @staticmethod
    def _load_game_data(game_data_fp):
        """Loads a YAML formatted SAF game file from disk"""
        yaml.add_constructor('!Scenes', _Scene.scenes_constructor, Loader=yaml.SafeLoader)
        with open(game_data_fp, 'r') as f:
            game_data = list(yaml.safe_load_all(stream=f))
        return game_data


class InputParser:
    """
    Converts Player inputs into action-keys that can then be used to find matching Actions for a Scene.

    Args:
        stop_words (iter of str): short words that should be excluded when creating action-keys
        synonyms (dict): mappings from synonyms (take, grab) to a canonical version (get)
    """

    def __init__(self, stop_words, synonyms):
        self._stop_words = stop_words
        self._synonyms = synonyms

    def generate_action_key(self, text_input):
        """
        Converts a player input to an action-key by removing stopwords and converting synonyms to their
        canonical versions.

        Returns:
            An action-key (set)
        """
        important_words = [w for w in text_input.split(' ') if w not in self._stop_words]
        translated_action_key = {self._synonyms[w] if w in self._synonyms else w for w in important_words}
        return translated_action_key

    @classmethod
    def construct_from_yaml(cls, parsing_data_fp):
        """
        Constructs an InputParser from an appropriately formatted YAML file.

        Example YAML file::

            --- !Parsing
                small_words:
                  - a
                  - an
                  - the
                  - in
                  - 'on'  # NOTE: 'on' without quotes is converted to True

                translations:
                  catch: get
                  pick: get
                  take: get
                  scoop: get
                  fill: get
                  collect: get

        Args:
            parsing_data_fp (str): file path of a YAML encoded parsing data

        Returns:
            An InputParser
        """
        def constructor(loader, node):
            """defines a constructor for a PyYAML loader"""
            data = loader.construct_mapping(node, deep=True)
            small_words = data['small_words']
            translations = data['translations']
            return cls(small_words, translations)

        yaml.add_constructor('!Parsing', constructor, Loader=yaml.SafeLoader)
        with open(parsing_data_fp, 'r') as f:
            input_parser = yaml.safe_load(stream=f)
        return input_parser


class _Scene:
    """
    Scene object containing a list of possible actions.

    Args:
        stop_words (iter of str): short words that should be excluded when creating action-keys
        synonyms (dict): mappings from synonyms (take, grab) to a canonical version (get)
    """
    def __init__(self, name):
        self.name = name
        self.actions = []

    @staticmethod
    def scenes_constructor(loader, node):
        data = loader.construct_mapping(node, deep=True)
        scenes = {scene_name: _Scene(scene_name) for scene_name in data.keys()}
        for scene_name, scene_data in data.items():
            for action_key, outcomes_data in scene_data['actions'].items():
                scenes[scene_name].actions.append(_Action(action_key, outcomes_data))
        return scenes


class _Action:

    def __init__(self, action_key, outcomes_data):
        self.key_set = {action_key}
        self.outcomes = [_Outcome.constructor(outcome_data) for outcome_data in outcomes_data]
        self.check_outcomes()

    def check_outcomes(self):
        # TODO
        pass


class _Outcome:

    def __init__(self, requirements, mutators, text, clear):
        self.requirements = requirements
        self.mutators = mutators
        self.text = text
        self.clear = clear

    def check_reqs(self, game):
        return all(requirement.check(game) for requirement in self.requirements)

    @staticmethod
    def constructor(outcome_data):

        requirements = []
        if 'reqs' in outcome_data:
            for req_type, targets in outcome_data['reqs'].items():
                for target in targets:
                    requirements.append(_Requirement.constructor(req_type, target))

        clear = False
        mutators = []
        if 'mutators' in outcome_data:
            for mutator_type, targets in outcome_data['mutators'].items():
                if mutator_type == 'player_move_to':
                    clear = True
                for target in targets:
                    mutators.append(_StateMutator.constructor(mutator_type, target))

        text = None
        if 'text' in outcome_data:
            text = outcome_data['text']
            text = [text] if isinstance(text, str) else text

        return _Outcome(requirements, mutators, text, clear)


class _Requirement:

    def __init__(self, test_func):
        self.test_func = test_func

    def check(self, game):
        return self.test_func(game)

    @staticmethod
    def constructor(req_type, target):
        return _Requirement(test_func=_Requirement.make_check_fnc(req_type, target))

    @staticmethod
    def make_check_fnc(req_type, target):

        if req_type == 'has_item':
            def check_func(game):
                return target in game.player.inventory
        elif req_type == 'not_has_item':
            def check_func(game):
                return target not in game.player.inventory
        elif req_type == 'has_state':
            def check_func(game):
                return target in game.player.states
        elif req_type == 'not_has_state':
            def check_func(game):
                return target not in game.player.states
        elif req_type == 'has_visited':
            def check_func(game):
                return target in game.player.visited_scene_names
        elif req_type == 'not_has_visited':
            def check_func(game):
                return target not in game.player.visited_scene_names
        else:
            raise ValueError

        return check_func


class _StateMutator:

    def __init__(self, mutator_func):
        self.mutator_func = mutator_func

    @staticmethod
    def constructor(mutator_type, target):
        return _StateMutator(mutator_func=_StateMutator.make_mutator_func(mutator_type, target))

    @staticmethod
    def make_mutator_func(mutator_type, target):

        if mutator_type == 'player_move_to':
            def mutator_func(game):
                game.player.current_scene = game.scenes[target]
                game._play('_arrive')
        elif mutator_type == 'player_arrive':
            def mutator_func(game):
                game.player.visited_scene_names.add(game.scenes[target].name)
        elif mutator_type == 'add_item':
            def mutator_func(game):
                game.player.inventory.add(target)
        elif mutator_type == 'remove_item':
            def mutator_func(game):
                game.player.inventory.remove(target)
        elif mutator_type == 'add_state':
            def mutator_func(game):
                game.player.states.add(target)
        elif mutator_type == 'remove_state':
            def mutator_func(game):
                game.player.states.remove(target)
        elif mutator_type == 'game_end':
            def mutator_func(game):
                game._in_progress = False
        else:
            raise ValueError('"{}" is not a valid mutator type'.format(mutator_type))
        return mutator_func


class Shell:

    def __init__(self, width, indentation='    '):
        self.usable_width = width - 2 * len(indentation)
        self.indentation = indentation

    def print(self, paragraphs, alignment):
        for paragraph in paragraphs:
            if alignment == 'left':
                print(indent(text=fill(text=paragraph, width=self.usable_width), prefix=self.indentation))
            elif alignment == 'centre':
                lines = wrap(text=paragraph, width=self.usable_width)
                print(*[self.indentation + str.center(l, self.usable_width) for l in lines], sep='\n')
            print()  # pad bottom of paragraphs

    def get_player_input(self, message=None):
        # TODO add some checks in here
        player_input = None
        while not player_input:
            if message:
                message = message + ' > '
            else:
                message = '> '
            player_input = input(
                indent(
                    text=fill(text=message, width=self.usable_width, drop_whitespace=False),
                    prefix=self.indentation
                )
            ).lower()
            player_input = ''.join(cha for cha in player_input if cha.isalnum() or cha == ' ')
            print()  # pad player input
        return player_input

    def pause(self):
        if OS_NAME == 'nt':
            self.print(paragraphs=["Press any key to continue..."], alignment='left')
            _ = msvcrt.getch()
        else:
            command = 'read -s -n 1 -p "{i}Press any key to continue..."'.format(i=self.indentation)
            os.system(command=command)

    @staticmethod
    def clear():
        os.system(command='cls' if OS_NAME == 'nt' else 'clear')
        print()  # pad top of screen


class Player:

    def __init__(self, initial_scene, initial_inventory, states, visited_scene_names):
        self.current_scene = initial_scene
        self.inventory = initial_inventory
        self.states = states
        self.visited_scene_names = visited_scene_names

    def save(self, fp):
        with open(file=fp, mode='wb') as f:
            dump(obj=self, file=f)
