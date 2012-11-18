import threading
import os
import sys
import re
import sublime
import sublime_plugin

__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'lib')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

import lettuce

LOADING_STATUS_LENGTH = 25

PYTHON_EXTENSION = 'py'
FEATURES_EXTENSION = 'feature'

STEP_PATTERN = re.compile("@step\(u?[\'\\\"](?P<step_regex>.*)[\'\\\"]\)([\s.]*)" + \
    "(?P<step_function>def (?P<step_function_name>[\w\d\_]+)" + \
    "\s*\((?P<step_function_args>[\w\d\,\= ]*)\))", re.MULTILINE)
FEATURE_REGISTRY = []
FEATURE_STEP_REGISTRY = {}

QUEUE = {}

ERROR_MARKS_KEY = 'lettuce.feature.marks'


class StepLoader(threading.Thread):
    complete = 0
    total_count = 0
    load_count = 0

    def __init__(self, folders, python_files=[], feature_files=[]):
        self.folders = folders
        self.python_files = python_files
        self.feature_files = feature_files
        lettuce.core.STEP_REGISTRY = {}
        threading.Thread.__init__(self)

    def run(self):
        self.complete = 0
        self.total_count = 0
        self.load_count = 0
        self.init_files()
        self.load_steps()
        self.load_feature_files()

    def init_files(self):
        for folder in self.folders:
            for root, sub_folders, files in os.walk(folder):
                for file in files:
                    if file not in self.python_files \
                        and file not in self.feature_files:
                        extension = _get_file_extension(file)
                        if extension == PYTHON_EXTENSION:
                            self.python_files.append(os.path.join(root, file))
                        elif extension == FEATURES_EXTENSION:
                            self.feature_files.append(os.path.join(root, file))
        self.total_count = float(len(self.python_files)) + \
            float(len(self.feature_files))

    def load_steps(self):
        '''
        Scan python files in any projects or open files for @step decorators
        used by lettuce.
        '''
        for file in self.python_files:
            self.load_steps_in_file(file)
            self.load_count += 1
            self.complete = int(round((self.load_count / self.total_count) *
                LOADING_STATUS_LENGTH))

    @classmethod
    def load_steps_in_file(cls, file):
        ifile = open(file, 'r')
        text = ifile.read()
        ifile.close()
        for step in STEP_PATTERN.finditer(text):
            definition = step.group('step_regex')
            params = {
                'regex': definition,
                'function_name': step.group('step_function_name'),
                'function_args': step.group('step_function_args').split(', '),
            }

            def temp_func():
                return params

            if definition not in lettuce.core.STEP_REGISTRY.keys():
                lettuce.core.STEP_REGISTRY[definition] = temp_func

    def load_feature_files(self):
        for file in self.feature_files:
            StepLoader.load_features_in_file(file)
            self.load_count += 1
            self.complete = int(round(self.load_count / self.total_count) *
                LOADING_STATUS_LENGTH)

    @classmethod
    def load_features_in_file(cls, file):
        feature = lettuce.core.Feature.from_file(file)
        for scenario in feature.scenarios:
            for step in scenario.steps:
                try:
                    matched, definition = step.pre_run(True)
                except lettuce.exceptions.NoDefinitionFound:
                    pass
                FEATURE_STEP_REGISTRY[step.sentence] = \
                    StepLoader.tokenize_sentence(step, matched)

    @classmethod
    def tokenize_sentence(cls, step, regex):
        if regex.re.pattern in lettuce.core.STEP_REGISTRY:
            params = lettuce.core.STEP_REGISTRY[regex.re.pattern]()
            if 'step' in params['function_args']:
                params['function_args'].remove('step')
            token = regex.string
            offset = 0
            for i, match in enumerate(regex.groups()):
                replace = "<" + params['function_args'][i] + ">"
                start = regex.start(i + 1) + offset
                end = regex.end(i + 1) + offset
                token = token[:start] + replace + token[end:]
                offset = len(replace) - (regex.end(i + 1) - regex.start(i + 1))
            return token
        else:
            return step.sentence


class FeatureValidator(threading.Thread):

    def __init__(self, text, id):
        self.text = text
        self.id = id
        threading.Thread.__init__(self)

    def run(self):
        feature = lettuce.core.Feature.from_string(self.text)
        for scenario in feature.scenarios:
            for step in scenario.steps:
                try:
                    matched, definition = step.pre_run(True)
                except lettuce.exceptions.NoDefinitionFound:
                    QUEUE[self.id].append(step)


class LettuceFarmerEventListener(sublime_plugin.EventListener):
    is_active = False
    window = None

    def __init__(self):
        super(LettuceFarmerEventListener, self).__init__()
        _reload_step_definitions(sublime.active_window())

    def on_modified(self, view):
        if _get_file_extension(view.file_name()) == FEATURES_EXTENSION:
            _queue_validator(view)

    def on_activated(self, view):
        if _get_file_extension(view.file_name()) == FEATURES_EXTENSION:
            _queue_validator(view)
            self.is_active = True
        else:
            self.is_active = False

    def on_post_save(self, view):
        extension = _get_file_extension(view.file_name())
        if extension == PYTHON_EXTENSION:
            StepLoader.load_steps_in_file(view.file_name())
        elif extension == FEATURES_EXTENSION:
            StepLoader.load_features_in_file(view.file_name())
            _queue_validator(view)

    def on_query_completions(self, view, prefix, locations):
        if self.is_active:
            return ([(sentence, tokenized_sentence) \
                for sentence, tokenized_sentence \
                in FEATURE_STEP_REGISTRY.iteritems()],
                sublime.INHIBIT_WORD_COMPLETIONS)


class LettuceFarmer(sublime_plugin.TextCommand):

    def run(self, *args, **kwargs):
        action = kwargs.get('action')
        if action == 'reload':
            def reload_result(result):
                sublime.message_dialog(result)
            _reload_step_definitions(sublime.active_window(), reload_result)


def _queue_validator(view, callback=None):
    if view.id() in QUEUE.keys():
        return

    QUEUE[view.id()] = []
    text = view.substr(sublime.Region(0, view.size())).encode('utf-8')
    validator = FeatureValidator(text, view.id())
    validator.start()

    def _validator_callback():
        if len(QUEUE[view.id()]):
            _add_marks(QUEUE[view.id()], view)
        del QUEUE[view.id()]

    _handle_feature_validator(validator, callback=_validator_callback)


def _add_marks(steps, view):
    _erase_marks(view)
    regions = []
    for step in steps:
        if step.has_definition or len(step.sentence) < 3:
            continue

        if step.described_at.line:
            line = step.described_at.line
            lines = [view.full_line(view.text_point(line - 1, 0))]
        else:
            sentence = r"\s{%d}%s$" % (step.indentation, step.sentence)
            matches = view.find_all(sentence)
            lines = [view.full_line(region) for region in matches]
        regions.extend(lines)

    view.add_regions(ERROR_MARKS_KEY, regions, 'lettuce.feature.outline',
        'dot', sublime.DRAW_OUTLINED)


def _erase_marks(view):
    view.erase_regions(ERROR_MARKS_KEY)


def _handle_feature_validator(thread, callback=None):
    next_thread = None
    if thread.is_alive():
        next_thread = thread

    thread = next_thread
    if thread:
        sublime.set_timeout(lambda: _handle_feature_validator(thread, callback),
            50)
        return

    if callback:
        callback()


def _handle_step_loader(thread, window, callback=None):
    next_thread = None
    if thread.is_alive():
        next_thread = thread

    status_key = 'LettuceFarmer.loading_steps'
    thread = next_thread
    if thread:
        window.active_view().set_status(status_key,
            'Loading steps [%s%s]' % (
                "=" * thread.complete,
                "  " * int(LOADING_STATUS_LENGTH - thread.complete)))

        sublime.set_timeout(lambda: _handle_step_loader(thread, window,
            callback), 50)
        return

    window.active_view().erase_status(status_key)

    if callback:
        callback('Successfully loaded %d step definitions and %d steps.' %
            (len(lettuce.core.STEP_REGISTRY),
                len(FEATURE_STEP_REGISTRY.keys())))


def _reload_step_definitions(window, callback=None):
    _python_files_to_scan = []
    _feature_files_to_scan = []
    for view in window.views():
        extension = _get_file_extension(view.file_name())
        if extension == PYTHON_EXTENSION:
            _python_files_to_scan.append(view.file_name())
        elif extension == FEATURES_EXTENSION:
            _feature_files_to_scan.append(view.file_name())

    step_loader = StepLoader(window.folders(),
        python_files=_python_files_to_scan,
        feature_files=_feature_files_to_scan)
    step_loader.start()
    _handle_step_loader(step_loader, window, callback)


def _get_file_extension(file_name):
    if not file_name:
        return
    return file_name.split(".")[-1]
