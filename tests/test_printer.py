import pytest
import unittest.mock
from collections import namedtuple
from itertools import product
from skeleng import Printer

# Create important combinations of args
PrinterParams = namedtuple(typename='Params', field_names=['sys', 'width'])
sys_cmds = ('nt', 'cls'), ('posix', 'clear'), ('?', 'clear')
widths = [10, 280, 1000]
arg_grid = [(PrinterParams(sys, width), cmd) for (sys, cmd), width in product(sys_cmds, widths)]


def pytest_generate_tests(metafunc):
    if all(fn in metafunc.fixturenames for fn in ('printer', 'cmd')):
        metafunc.parametrize(
            argnames='printer, cmd',
            argvalues=arg_grid,
            indirect=['printer']
        )


@pytest.fixture
def printer(request):
    return Printer(width=request.param.width, system=request.param.sys)


@unittest.mock.patch('os.system')
def test_clear(os_system, printer, cmd):
    printer.clear_screen()
    os_system.assert_called_once_with(cmd)
