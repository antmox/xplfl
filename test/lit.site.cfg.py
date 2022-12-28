from lit import formats

config.name = 'XPLFL'

config.test_format = formats.ShTest(True)

config.suffixes = ['.sh']

config.test_exec_root = os.path.join(os.path.dirname(__file__), 'tests_tmp')

config.environment['XPLFL'] = os.path.dirname(os.path.dirname(__file__))

