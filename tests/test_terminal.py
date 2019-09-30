import pytest
from unittest import mock
from collections import namedtuple
from itertools import product
from engine import Terminal


TerminalParams = namedtuple(typename='Params', field_names=['os_name', 'width'])
sys_cmds = {'nt': 'cls', 'posix': 'clear'}
paragraphs = ['This is a test paragraph.', 'So is this.', '']
alignments = ['left', 'centre']
widths = [20, 40]
expected = {
    ('left', 20): '    This is a\n    test\n    paragraph.\n\n    So is this.\n\n\n\n',
    ('left', 40): '    This is a test paragraph.\n\n    So is this.\n\n\n\n',
    ('centre', 20): '     This is a  \n        test    \n     paragraph. \n\n    So is this. \n\n\n\n',
    ('centre', 40): '       This is a test paragraph.    \n\n              So is this.           \n\n\n\n'
}

clear_arg_grid = [(TerminalParams(os_name, 20), sys_cmds[os_name]) for os_name in sys_cmds.keys()]
print_arg_grid = [
    (TerminalParams('posix', width), paragraphs, alignment, expected[(alignment, width)])
    for alignment, width in product(alignments, widths)
]


@pytest.fixture
def terminal(request):
    return Terminal(width=request.param.width, os_name=request.param.os_name, indentation='    ')


@pytest.mark.parametrize(argnames='terminal, cmd', argvalues=clear_arg_grid, indirect=['terminal'])
def test_clear_screen(capsys, terminal, cmd):
    with mock.patch(target='os.system') as os_system:
        terminal.clear_screen()
        captured = capsys.readouterr()
        assert os_system.called_once_with(cmd)
        assert captured.out == '\n'


@pytest.mark.parametrize(
    argnames='terminal, paragraphs, alignment, expected', argvalues=print_arg_grid, indirect=['terminal']
)
def test_print(capsys, terminal, paragraphs, alignment, expected):
    with mock.patch(target='engine.Terminal.clear_screen'):
        terminal.print(paragraphs=paragraphs, alignment=alignment)
        out, err = capsys.readouterr()
        assert out == expected
        assert err == ''


# @pytest.mark.parametrize(
#     argnames='terminal, input', argvalues=print_arg_grid, indirect=['terminal']
# )
# def test_get_player_input(capsys, terminal, paragraphs, alignment, expected):
#     with mock.patch(target='engine.Terminal.clear_screen'):
#         terminal.print(paragraphs=paragraphs, alignment=alignment)
#         out, err = capsys.readouterr()
#         assert out == expected
#         assert err == ''
