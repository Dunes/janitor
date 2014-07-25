-"""
Created on 21 Jun 2014

@author: jack
"""
import unittest
from unittest.mock import patch, Mock, DEFAULT, call

from logger import Logger

from io import StringIO


# noinspection PyUnresolvedReferences
class LoggerTest(unittest.TestCase):

    def setUp(self):
        self.patch = patch.object(Logger, "__init__", return_value=None)  # @UndefinedVariable
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_get_log_file_name(self):
        expected = "problem_name-planning_time(0).log"
        actual = Logger.get_log_file_name("problem_name", 0)
        self.assertEqual(expected, actual)

    def test_get_plan_log_file_name(self):
        expected = "log_file_name-plans.log"
        actual = Logger.get_plan_log_file_name("log_file_name.log")
        self.assertEqual(expected, actual)

    @patch("logger.makedirs")
    def test_create_if_not_exists_not_exist(self, mocked_makedirs):
        path = "path"
        Logger("log_file_name")._create_if_not_exists(path)
        mocked_makedirs.assert_called_once_with(path)

    @patch.multiple("logger", makedirs=DEFAULT, isdir=DEFAULT)
    def test_create_if_not_exists_and_exists_as_dir(self, makedirs, isdir):
        path = "path"
        makedirs.side_effect = FileExistsError
        isdir.return_value = True

        Logger("log_file_name")._create_if_not_exists(path)

        makedirs.assert_called_once_with(path)
        isdir.assert_called_once_with(path)

    @patch.multiple("logger", makedirs=DEFAULT, isdir=DEFAULT)
    def test_create_if_not_exists_and_exists_as_not_dir(self, makedirs, isdir):
        path = "path"
        makedirs.side_effect = FileExistsError
        isdir.return_value = False

        self.assertRaises(FileExistsError, Logger("log_file_name")._create_if_not_exists, path)

        makedirs.assert_called_once_with(path)
        isdir.assert_called_once_with(path)

    def test_log_property(self):
        logger = Logger()
        logger.log = StringIO()

        logger.log_property("name", "value")

        self.assertEqual("'name': value,\n", logger.log.getvalue())

    def test_log_property_with_repr(self):
        logger = Logger()
        logger.log = StringIO()

        logger.log_property("name", "value", stringify=repr)

        self.assertEqual("'name': 'value',\n", logger.log.getvalue())

    @patch("logger.open", return_value=StringIO(), create=True)
    def test_log_property_log_not_open_yet(self, string_io_open):
        logger = Logger()
        logger.log_file_name = None
        logger.log = None

        logger.log_property("name", "value")

        self.assertEqual("{\n'name': value,\n", string_io_open().getvalue())

    def test_log_plan(self):
        logger = Logger()
        logger.plan_log = StringIO()

        logger.log_plan(["plan"])

        self.assertEqual("['plan']\n", logger.plan_log.getvalue())

    @patch("logger.open", return_value=StringIO(), create=True)
    def test_log_plan_log_not_open_yet(self, string_io_open):
        logger = Logger()
        logger.plan_log_file_name = None
        logger.plan_log = None

        logger.log_plan(["plan"])

        self.assertEqual("['plan']\n", string_io_open().getvalue())

    def test_close(self):
        logger = Logger()
        logger.log = Mock()
        logger.log.closed = False
        logger.plan_log = Mock()
        logger.plan_log.closed = False

        logger.close()

        logger.log.write.assert_called_once_with("}\n")
        logger.log.close.assert_called_once_with()
        logger.plan_log.close.assert_called_once_with()

    def test_close_when_already_closed(self):
        logger = Logger()
        logger.log = Mock()
        logger.log.closed = True
        logger.plan_log = Mock()
        logger.plan_log.closed = True

        logger.close()

        self.assertEqual(False, logger.log.write.called)
        self.assertEqual(False, logger.log.close.called)
        self.assertEqual(False, logger.plan_log.close.called)

    def test_close_re_raise_io_error(self):
        logger = Logger()
        logger.log = Mock()
        logger.log.closed = False
        logger.log.write.side_effect = IOError
        logger.plan_log = Mock()
        logger.plan_log.closed = False

        self.assertRaises(IOError, logger.close)

        logger.log.write.assert_called_once_with("}\n")
        self.assertEqual(False, logger.log.close.called)
        logger.plan_log.close.assert_called_once_with()


class LoggerInitTest(unittest.TestCase):

    # noinspection PyUnresolvedReferences
    @patch.object(Logger, "get_plan_log_file_name")
    @patch.object(Logger, "_create_if_not_exists")
    def test_init(self, _create_if_not_exists, get_plan_log_file_name):
        working_directory = "working_directory"
        plans_subdir = "plans_subdir"
        log_file_name = "log_file_name"
        get_plan_log_file_name.return_value = log_file_name

        log = Logger(log_file_name, working_directory, plans_subdir)

        self.assertEqual(2, _create_if_not_exists.call_count)
        _create_if_not_exists.assert_has_calls([
            call(working_directory),
            call("working_directory/plans_subdir"),
        ])
        self.assertEqual("working_directory/log_file_name", log.log_file_name)
        self.assertEqual("working_directory/plans_subdir/log_file_name", log.plan_log_file_name)
        self.assertEqual(None, log.log)
        self.assertEqual(None, log.plan_log)


if __name__ == "__main__":
    unittest.main()