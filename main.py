import csv
import weakref
from collections import defaultdict

from pymystem3 import Mystem

m = Mystem()


class DialogWord:
    next = None

    def __init__(self, word=None, lex=None, wt=None, gr=None, message=None, dialog=None, prev=None):
        self.message = message
        self.dialog = dialog
        self.word = word
        self.lex = lex
        self.wt = wt
        self.gr = gr
        self.prev = prev
        if prev and isinstance(prev, DialogWord):
            prev.bind_next(self)

    def bind_next(self, next_word):
        self.next = next_word

    def check_greeting(self):
        if self.lex == 'здравствовать':
            self.dialog.bind_greeting_msg(self.message)

        if self.prev:
            if self.prev.lex == 'добрый' and self.gr.startswith('S'):
                self.dialog.bind_greeting_msg(self.message)

    def check_goodbye(self):
        if self.prev:
            if self.prev.lex == 'до' and self.lex in ['свидание', 'встреча']:
                self.dialog.bind_goodbye_msg(self.message)

            if self.prev.word.lower() == 'всего' and self.lex in ['добрый', 'хороший']:
                self.dialog.bind_goodbye_msg(self.message)

    def check_manager_name(self):
        if self.prev:
            if self.prev.prev:
                if self.gr.startswith('S,имя'):
                    if self.prev.lex == 'это' and self.prev.prev.word.lower() == 'да':
                        self.dialog.bind_manager_name(self.message, self.word)

                    if self.prev.lex in ['звать', 'имя'] and self.prev.prev.lex == 'я':
                        self.dialog.bind_manager_name(self.message, self.word)

                if self.lex == 'звать' and self.prev.gr.startswith('S,имя') and self.prev.prev.lex == 'я':
                    self.dialog.bind_manager_name(self.message, self.word)

    def check_company_name(self):
        if self.prev:
            if self.prev.prev:
                if not self.gr.startswith('V') or not self.gr.startswith('ADV'):
                    if self.prev.lex == 'компания':
                        self.dialog.bind_company_name(self.message, self.word)
                    if self.prev.prev.lex == 'компания':
                        self.dialog.bind_company_name(self.message, f'{self.prev.word} {self.word}')

    def analyze_prev_words(self):
        if self.message.role == 'manager':
            if not self.dialog.manager_greeting_msg:
                self.check_greeting()

            elif not self.dialog.manager_goodbye_msg:
                self.check_goodbye()

            else:
                self.dialog.manager_requirement = True

            if not self.dialog.manager_name_msg:
                self.check_manager_name()

            if not self.dialog.company_name_msg or \
                    self.dialog.company_name_msg == self.message:
                self.check_company_name()


class DialogMessage(object):
    __refs__ = defaultdict(list)

    insight = ''
    words = []

    def __init__(self, line, role, text=None, dialog=None):
        self.__refs__[self.__class__].append(weakref.ref(self))

        self.line = line
        self.role = role
        self.text = text
        self.dialog = dialog

    @classmethod
    def get_instances(cls):
        for inst_ref in cls.__refs__[cls]:
            inst = inst_ref()
            if inst is not None:
                yield inst

    def analyze_message(self):
        dict_words = m.analyze(self.text)
        _prev_word = None
        for _word in dict_words:
            if not _word.get('analysis', None):
                continue
            word_inst = DialogWord(
                word=_word['text'],
                lex=_word['analysis'][0].get('lex', None),
                wt=_word['analysis'][0].get('wt', None),
                gr=_word['analysis'][0].get('gr', None),
                dialog=self.dialog,
                message=self,
                prev=_prev_word
            )
            word_inst.analyze_prev_words()
            self.words.append(word_inst)
            _prev_word = word_inst


class Dialog:
    words = []
    messages = []
    manager_greeting_msg = None
    manager_introduced_msg = None
    manager_name_msg = None
    manager_name = None
    company_name_msg = None
    company_name = None
    manager_goodbye_msg = None
    manager_requirement = False

    def __init__(self, dlg_id):
        self.dlg_id = dlg_id

    def add_message(self, message: DialogMessage):
        self.messages.append(message)

    def get_massages_count(self):
        return len(self.messages)

    def bind_greeting_msg(self, message):
        self.manager_greeting_msg = message
        message.insight += 'greeting=True '

    def bind_goodbye_msg(self, message):
        self.manager_goodbye_msg = message
        message.insight += 'goodbye=True '

    def bind_manager_name_msg(self, message):
        self.manager_name_msg = message
        message.insight += 'm_name=True '

    def bind_manager_name(self, message, name):
        self.bind_manager_name_msg(message)
        self.manager_name = name

    def bind_company_name_msg(self, message):
        self.company_name_msg = message
        if not 'c_name=True ' in message.insight:
            message.insight += 'c_name=True '

    def bind_company_name(self, message, name):
        self.bind_company_name_msg(message)
        self.company_name = name


def reading_csv_file(file_path: str) -> list:
    """
    :param file_path:
    :return:
    """

    if not file_path.endswith('.csv'):
        raise ImportError('Csv reader can not read this file: %s' % file_path)

    with open(file_path, encoding='utf-8-sig') as csv_file:
        dialogs_data = csv.DictReader(csv_file)
        return list(dialogs_data)


def parse_dialogs(dialogs_data: list) -> dict:
    _dialogs = {}
    for dialog_data in dialogs_data:
        print(f'{dialog_data["dlg_id"]}-{dialog_data["line_n"]}-{dialog_data["text"]}')
        if not _dialogs.get(dialog_data['dlg_id'], False):
            _dialog = Dialog(dialog_data['dlg_id'])
            _dialogs[dialog_data['dlg_id']] = _dialog
        else:
            _dialog = _dialogs.get(dialog_data['dlg_id'], None)
        massage = DialogMessage(
            line=dialog_data['line_n'],
            role=dialog_data['role'],
            text=dialog_data['text'],
            dialog=_dialog
        )
        massage.analyze_message()
        _dialogs[dialog_data['dlg_id']].add_message(
            massage
        )
    return _dialogs


def write_result_to_cvs(dialogs_for_export_to_cvs, file_name):
    header = ['dlg_id', 'line_n', 'role', 'text', 'insight']
    cvs_data = []
    for _dlg_id, _dialog in dialogs_for_export_to_cvs.item():
        for _message in _dialog.messages:
            cvs_data.append([
                _dlg_id,
                _message.line,
                _message.role,
                _message.text,
                _message.insight,
            ])

    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)

        # write the header
        writer.writerow(header)

        # write multiple rows
        writer.writerows(cvs_data)


if __name__ == '__main__':
    data = reading_csv_file('test_data.csv')
    dialogs = parse_dialogs(data)
    write_result_to_cvs(dialogs, 'test_data_result.csv')
