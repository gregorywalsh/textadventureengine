# Created by Gregory Walsh

"""
This module contains the necessary classes required to run a YAML Adventure File (YAF)
and an associated Input Parsing File (IPF).
"""

import os
import yaml
from collections import defaultdict
from functools import partial
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
        player (Player): The Player of the game
        shell (Shell): The Game's shell. Can be used to print messages
    """

    def __init__(self, game_data_fp, input_parser, shell, player):
        self.player = player
        self.shell = shell
        self._input_parser = input_parser
        self._metadata, self.scenes = Game._load_game_data(self, game_data_fp)
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
        self._play(override_input=self._metadata['first_action'])
        while self._in_progress:
            self._play()

    def _play(self, override_input=None):
        """ Performs a single game loop:
            request input -> find matching Action -> determine Outcome and execute associated Mutators
        """
        text_input = override_input or self.shell.get_player_input()
        input_action_key = self._input_parser.generate_action_key(text_input=text_input)
        action = self._match_action(input_action_key=input_action_key)
        outcome = self._match_outcome(action)
        if outcome:
            self._process_outcome(outcome)
        else:
            self.shell.print(
                paragraphs=['You cannot do that now.'],
                alignment='left'
            )

    def _match_action(self, input_action_key):
        """ Given an input, returns the first matching Action. Falls back to a default if there is one."""
        get_action = self.player.current_scene.actions.get
        return get_action(input_action_key) or get_action(frozenset(['_no_match']))

    def _match_outcome(self, action):
        """ Given an Action, returns the first possible matching Outcome by checking requirements against
            the Player's state.
            Examples:
                1. Player WITHOUT 'knife' attempts cut 'rope' by inputting "cut rope". The outcome may
                   be that the rope remains intact, and a msg saying so could be displayed.
                2. Player WITH 'knife' attempts cut 'rope' by inputting "cut rope". The outcome may
                   be that the rope is cut and placed in their inventory. A msg saying so could also be displayed.
        """
        matched_outcomes = [outcome for outcome in action.outcomes if outcome.check_requirements(self.player)]
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

    def _load_game_data(self, game_data_fp):
        """Loads a YAML Adventure File (game metadata and a list of Scenes) from disk"""
        yaml.add_constructor(tag='!Scene', constructor=_Scene.pyyaml_constructor, Loader=yaml.SafeLoader)
        action_constructor = _Action.make_pyyaml_constructor(input_parser=self._input_parser)
        yaml.add_constructor(tag='!Action', constructor=action_constructor, Loader=yaml.SafeLoader)
        yaml.add_constructor(tag='!Outcome', constructor=_Outcome.pyyaml_constructor, Loader=yaml.SafeLoader)
        yaml.add_constructor(tag='!Mutator', constructor=_Mutator.construct_from_yaml, Loader=yaml.SafeLoader)
        # yaml.add_constructor(tag='!Requirement', constructor=_Requirement.construct_from_yaml, Loader=yaml.SafeLoader)
        with open(game_data_fp, 'r') as f:
            meta_data, scenes = list(yaml.safe_load_all(stream=f))
        return meta_data, {scene.key: scene for scene in scenes}


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
            An action-key (frozenset)
        """
        important_words = [w for w in text_input.split(' ') if w not in self._stop_words]
        translated_action_key = frozenset(self._synonyms[w] if w in self._synonyms else w for w in important_words)
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
    Scene object containing a list of possible Actions.

    Example YAML element::
    - !Scene
      id: a_unique_scene_id
      actions:
        [A LIST OF ACTIONS HERE]

    Args:
        key (str): name of the Scene
        actions_list (list of Actions): list containing all possible actions in a Scene

    Attributes:
        key (str): name of the Scene
        actions (dict of Actions): dict containing all possible actions in a Scene by their key
    """
    def __init__(self, key, actions_list):
        self.key = key
        self.check_duplicate_action_keys(actions_list)
        self.actions = {action.key: action for action in actions_list}

    def check_duplicate_action_keys(self, actions_list):
        if len(set(action.key for action in actions_list)) != len(actions_list):
            raise ValueError('Duplicate action key (after parsing) found in Scene: "{s}"'.format(s=self.key))

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """PyYAML constructor that generates a Scene from a YAF element tagged with '!Scene' """
        data = loader.construct_mapping(node, deep=True)
        return cls(key=data['key'], actions_list=data['actions'])


class _Action:
    """
    Action object containing a list of possible Outcomes. The id is matched against the player input

    Args:
        key (frozenset): a set of keywords that uniquely identifies the Action per scene
        outcomes (list of Outcomes): list containing all possible Outcomes for the Action

    Attributes:
        key (frozenset): a unique set of keywords that identify the Action
        outcomes (list of Outcomes): list containing all possible Outcomes for the Action
    """

    def __init__(self, key, outcomes):
        self.key = key
        self.outcomes = outcomes
        self._check_outcomes()

    @classmethod
    def make_pyyaml_constructor(cls, input_parser):
        def pyyaml_constructor(loader, node):
            """PyYAMP constructor that generates an Action from a YAF element tagged with '!Action' """
            data = loader.construct_mapping(node, deep=True)
            key = input_parser.generate_action_key(data['key'])
            return cls(key=key, outcomes=data['outcomes'])
        return pyyaml_constructor

    def _check_outcomes(self):
        # TODO
        pass


class _Outcome:

    def __init__(self, clear, requirements=None, mutators=None, text=None):
        self.requirements = requirements if requirements else []
        self.mutators = mutators if mutators else []
        self.text = text if text else []
        self.clear = clear

    def check_requirements(self, player):
        return all(requirement.check(player) for requirement in self.requirements)

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """PyYAML constructor that generates an Outcome from a YAF element tagged with '!Outcome' """
        data = loader.construct_mapping(node, deep=True)
        return cls(requirements=data.get('requirements'), mutators=data.get('mutators'),
                   text=data.get('text'), clear=False)


class _Requirement:

    def __init__(self, test_func):
        self.test_func = test_func

    def check(self, player):
        return self.test_func(player)

    @classmethod
    def pyyaml_constructor(cls, loader, node):
        """PyYAML constructor that generates an Outcome from a YAF element tagged with '!Outcome' """
        data = loader.construct_mapping(node, deep=True)
        return cls(test_func=_Requirement.make_check_fnc(type_=data.get('type'), target=data.get('target')))

    @staticmethod
    def make_check_fnc(type_, target):
        if type_ == 'has_item':
            def check_func(player):
                return target in player.inventory
        elif type_ == 'not_has_item':
            def check_func(player):
                return target not in player.inventory
        elif type_ == 'has_state':
            def check_func(player):
                return target in player.states
        elif type_ == 'not_has_state':
            def check_func(player):
                return target not in player.states
        elif type_ == 'has_visited':
            def check_func(player):
                return target in player.visited_scene_names
        elif type_ == 'not_has_visited':
            def check_func(player):
                return target not in player.visited_scene_names
        else:
            raise ValueError
        return check_func


class _Mutator:

    def __init__(self, mutator_func):
        self.mutator_func = mutator_func

    @classmethod
    def construct_from_yaml(cls, loader, node):
        """PyYAMP constructor that generates an Outcome from a YAF element tagged with '!Outcome' """
        data = loader.construct_mapping(node, deep=True)
        return cls(mutator_func=_Mutator.make_mutator_func(type_=data.get('type'), target=data.get('target')))

    @staticmethod
    def make_mutator_func(type_, target):

        if type_ == 'player_move_to':
            def mutator_func(game):
                game.player.current_scene = game.scenes[target]
                game._play('_arrive')
        elif type_ == 'player_arrive':
            def mutator_func(game):
                game.player.visited_scene_names.add(game.scenes[target].key)
        elif type_ == 'add_item':
            def mutator_func(game):
                game.player.inventory.add(target)
        elif type_ == 'remove_item':
            def mutator_func(game):
                game.player.inventory.remove(target)
        elif type_ == 'add_state':
            def mutator_func(game):
                game.player.states.add(target)
        elif type_ == 'remove_state':
            def mutator_func(game):
                game.player.states.remove(target)
        elif type_ == 'game_end':
            def mutator_func(game):
                game._in_progress = False
        else:
            raise ValueError('"{}" is not a valid mutator type'.format(type_))
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
        if message:
            message = message + ' > '
        else:
            message = '> '
        while not player_input:
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
