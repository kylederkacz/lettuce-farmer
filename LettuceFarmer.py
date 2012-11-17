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

STEP_PATTERN = "@step\(u?[\'\\\"](?P<step_regex>.*)[\'\\\"]\)([\s.]*)" + \
    "(?P<step_function>def (?P<step_function_name>[\w\d\_]+)" + \
    "\s*\((?P<step_function_args>[\w\d\,\= ]*)\))"
FEATURE_REGISTRY = []
FEATURE_STEP_REGISTRY = {}


class StepLoader(threading.Thread):
    step_pattern = re.compile(STEP_PATTERN, re.MULTILINE)
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
        self.load_features()

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

    def load_steps_in_file(self, file):
        ifile = open(file, 'r')
        text = ifile.read()
        ifile.close()
        for step in self.step_pattern.finditer(text):
            definition = step.group('step_regex')
            params = {
                'regex': definition,
                'function_name': step.group('step_function_name'),
                'function_args': step.group('step_function_args'),
            }

            def temp_func():
                return params

            if definition not in lettuce.core.STEP_REGISTRY.keys():
                lettuce.core.STEP_REGISTRY[definition] = temp_func

    def load_features(self):
        for file in self.feature_files:
            FEATURE_REGISTRY.append(lettuce.core.Feature.from_file(file))
            self.load_count += 1
            self.complete = int(round(self.load_count / self.total_count) *
                LOADING_STATUS_LENGTH)

        for feature in FEATURE_REGISTRY:
            for scenario in feature.scenarios:
                for step in scenario.steps:
                    matched, definition = step.pre_run(True)
                    FEATURE_STEP_REGISTRY[step.sentence] = \
                        self._tokenize_sentence(step, matched)

    def _tokenize_sentence(self, step, regex):
        return step.sentence


class LettuceFarmerEventListener(sublime_plugin.EventListener):
    is_active = False
    window = None

    def __init__(self):
        super(LettuceFarmerEventListener, self).__init__()
        _reload_step_definitions(sublime.active_window())

    def on_activated(self, view):
        if _get_file_extension(view.file_name()) == 'feature':
            self.is_active = True
        else:
            self.is_active = False

    def on_post_save(self, view):
        extension = _get_file_extension(view.file_name())
        if extension == PYTHON_EXTENSION:
            steps = view.find_all("@step\(u?[\'\\\"](.*)[\'\\\"]\)")
            for step in steps:
                print view.substr(step)

            # TODO: Update the step definitions
            pass
        elif extension == 'feature':
            pass

    def on_query_completions(self, view, prefix, locations):
        if self.is_active:
            return ([(sentence, tokenized_sentence) \
                for sentence, tokenized_sentence \
                in FEATURE_STEP_REGISTRY.iteritems()],
                sublime.INHIBIT_WORD_COMPLETIONS)


class LettuceFarmer(sublime_plugin.TextCommand):

    def run(self, *args, **kwargs):
        action = kwargs.get('action')
        print self.view.settings().get('auto_complete_selector')
        if action == 'reload':
            def reload_result(result):
                sublime.message_dialog(result)
            _reload_step_definitions(sublime.active_window(), reload_result)

    def is_visible(self):
        '''
        Determine if the menu items are available
        '''
        return True


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

    sublime.set_timeout(lambda: window.active_view().erase_status(status_key),
        500)

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
