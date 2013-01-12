import os

from filefactory import FileFactory

class Action:
    NORMAL = 0
    WARNING = 1
    DANGER = 2

    def __init__(self, severity, description, undo):
        self.severity = severity
        self.description = description
        self.undo = undo

class FileList:
    def __init__(self):
        self.files = None

    def set_files(self, files):
        self.files = files

    def get_item_at(self, index):
        return self.files[index % len(self.files)]

    def get_length(self):
        return len(self.files)

    def is_empty(self):
        return not self.files

    def insert(self, pos, item):
        self.files.insert(pos, item)

    def remove(self, pos):
        del self.files[pos]

    def find(self, filename):
        return self.files.index(filename)

    def sort(self, key, reverse):
        self.files = sorted(self.files, key, reverse)

class FileManager:
    def __init__(self, on_list_empty, on_list_modified):
        self.filelist = FileList()
        self.index = 0

        self.on_list_empty = on_list_empty
        self.on_list_modified = on_list_modified

    def set_files(self, files):
        self.filelist.set_files(map(FileFactory.create, files))

    def get_current_file(self):
        return self.filelist.get_item_at(self.index)

    def get_prev_file(self):
        return self.filelist.get_item_at(self.index - 1)

    def get_next_file(self):
        return self.filelist.get_item_at(self.index + 1)

    def get_current_index(self):
        return self.index

    def get_list_length(self):
        return self.filelist.get_length()

    def empty(self):
        return self.filelist.is_empty()

    def go_first(self):
        self.index = 0
        self.on_list_modified()

    def go_last(self):
        self.index = self.filelist.get_length() - 1
        self.on_list_modified()

    def go_forward(self, steps):
        self.index += steps
        if self.index >= self.filelist.get_length():
            self.index = self.index - self.filelist.get_length()
        self.on_list_modified()

    def go_backward(self, steps):
        self.index -= steps
        if self.index < 0:
            self.index = self.filelist.get_length() + self.index
        self.on_list_modified()

    def go_file(self, filename):
        self.index = self.filelist.find(filename)
        self.on_list_modified()

    def sort_by_date(self, reverse):
        filename = self.get_current_file().get_filename()
        self.filelist.sort(key=lambda file_: file_.get_mtime(),
                           reverse=reverse)
        self.go_file(filename)

    def sort_by_name(self, reverse):
        filename = self.get_current_file().get_filename()
        self.filelist.sort(key=lambda file_: file_.get_filename(),
                           reverse=reverse)
        self.go_file(filename)

    def rename_current(self, new_filename):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_dirname = current.get_dirname()
        orig_filename = current.get_filename()
        current.rename(new_filename)

        if os.path.abspath(orig_dirname) == os.path.abspath(current.get_dirname()):
            self.on_list_modified()

            def undo_action():
                current.rename(orig_filename)
                self.index = self.filelist.find(orig_filename)
                self.on_list_modified()
        else:
            self.on_current_eliminated()
            
            def undo_action():
                restored = FileFactory.create(new_filename)
                restored.rename(orig_filename)
                self.filelist.insert(orig_index, restored)
                self.index = self.filelist.find(orig_filename)
                self.on_list_modified()

        return Action(Action.NORMAL,
                      "'%s' renamed to '%s'" % (orig_filename, new_filename),
                      undo_action)

    def move_current(self, target_dir, target_name=''):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_filename = current.get_filename()

        if not target_name:
            target_name = current.get_basename()

        new_filename = os.path.join(target_dir, target_name)

        if os.path.isfile(new_filename):
            return self.handle_duplicate(target_dir, target_name)

        current.rename(new_filename)
        self.on_current_eliminated()

        def undo_action():
            restored = FileFactory.create(new_filename)
            restored.rename(orig_filename)
            self.filelist.insert(orig_index, restored)
            self.index = self.filelist.find(orig_filename)
            self.on_list_modified()

        return Action(Action.NORMAL,
                      "'%s' moved to '%s'" % (orig_filename, target_dir),
                      undo_action)

    def delete_current(self):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_filename = current.get_filename()

        current.trash()
        self.on_current_eliminated()

        def undo_action():
            restored = FileFactory.create(orig_filename)
            restored.untrash()
            self.filelist.insert(orig_index, restored)
            self.index = self.filelist.find(orig_filename)
            self.on_list_modified()

        return Action(Action.DANGER,
                      "'%s' deleted" % (orig_filename),
                      undo_action)

    def toggle_star(self):
        current = self.get_current_file()
        orig_filename = current.get_filename()
        prev_status = current.is_starred()
        current.set_starred(not prev_status)
        self.on_list_modified()

        def undo_action():
            current.set_starred(prev_status)
            self.index = self.filelist.find(orig_filename)
            self.on_list_modified()

        return Action(Action.NORMAL,
                      "'%s' %s" % (current.get_basename(), "unstarred" if prev_status else "starred"),
                      undo_action)

    # Internal helpers:
    def get_safe_candidate(self, target):
        filename = self.get_current_file().get_filename()
        candidate = os.path.basename(filename)

        index = 0
        while os.path.isfile(os.path.join(target, candidate)):
            name = os.path.basename(''.join(filename.split('.')[:-1]))
            ext = filename.split('.')[-1]
            index += 1
            candidate = "%s (%d).%s" % (name, index, ext)

        return candidate

    def handle_duplicate(self, target_dir, target_name):
        current = self.get_current_file()
        orig_filename = current.get_filename()
        new_file = FileFactory.create(os.path.join(target_dir, target_name))

        if current.get_sha1() == new_file.get_sha1():
            action = self.delete_current()
            action.description = "'%s' deleted to avoid duplicates" % orig_filename
            return action
        else:
            candidate = self.get_safe_candidate(target_dir)
            action = self.move_current(target_dir, candidate)
            action.severity = Action.WARNING
            action.description = "'%s' auto-renamed to '%s' in '%s'" % (orig_filename, candidate, target_dir)
            return action

    def on_current_eliminated(self):
        self.filelist.remove(self.index)

        if self.filelist.is_empty():
            self.on_list_empty()
        else:
            if self.index >= self.filelist.get_length():
                self.index = self.index - self.filelist.get_length()
            self.on_list_modified()

