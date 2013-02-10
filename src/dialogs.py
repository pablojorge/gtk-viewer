import time
import datetime
import gtk

class AboutDialog:
    def __init__(self, parent):
        self.window = gtk.Dialog(title="About", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_markup("<span size=\"large\">Viewer</span>\n\n" +
                         "Simple Multimedia Viewer")
        self.window.action_area.pack_start(label, True, True, 5)

    def show(self):
        self.window.show_all()

class TabbedInfoDialog:
    def __init__(self, parent, info):
        self.window = gtk.Dialog(title="Information", parent=parent, flags=gtk.DIALOG_MODAL)

        table = gtk.Table(rows=len(info), columns=len(info[0]))
        table.set_col_spacings(20)

        # Build the header
        for index, column in enumerate(info[0]):
            label = gtk.Label()
            label.set_markup("<b>%s</b>" % column)
            label.set_alignment(0, 0.5)
            table.attach(label, index, index+1, 0, 1)

        # Build the rows
        for index_y, row in enumerate(info[1:]):
            for index_x, column in enumerate(row):
                label = gtk.Label(str=column)
                label.set_alignment(0, 0.5)
                table.attach(label, index_x, index_x+1, index_y + 1, index_y + 2)

        self.window.action_area.pack_start(table, True, True, 5)

    def show(self):
        self.window.show_all()

class InfoDialog:
    def __init__(self, parent, message):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_INFO,
                                    gtk.BUTTONS_OK,
                                    message)

    def run(self):
        self.md.run()
        self.md.destroy()

class ErrorDialog:
    def __init__(self, parent, message):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_ERROR,
                                    gtk.BUTTONS_OK,
                                    message)

    def run(self):
        self.md.run()
        self.md.destroy()

class QuestionDialog:
    def __init__(self, parent, question):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_QUESTION,
                                    gtk.BUTTONS_YES_NO,
                                    question)

    def run(self):
        response = self.md.run()
        self.md.destroy()
        return response == gtk.RESPONSE_YES

class TextEntryDialog:
    def __init__(self, parent, text, default="", callback=None):
        self.callback = callback

        self.window = gtk.Dialog(title="", 
                                 parent=parent, 
                                 flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text(text)
        self.window.action_area.pack_start(label, True, True, 5)

        self.entry = gtk.Entry()
        self.entry.set_text(default)
        self.entry.connect("activate", self.on_entry_activate)
        self.window.action_area.pack_start(self.entry, True, True, 5)

        self.response = None

    def on_entry_activate(self, entry):
        text = entry.get_text()
        if text:
            if self.callback:
                self.callback(text)
            self.response = text
            self.window.response(0) # exit Dialog.run() sub-loop

    def run(self):
        self.window.show_all()
        self.window.run()
        gtk.Widget.destroy(self.window)
        return self.response

class NewFolderDialog(TextEntryDialog):
    def __init__(self, parent, callback):
        TextEntryDialog.__init__(self, parent=parent,
                                       text="Enter new folder name:",
                                       callback=callback)

class ProgressBarDialog:
    def __init__(self, parent, text):
        self.window = gtk.Dialog(title="Progress", 
                                 parent=parent, 
                                 flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text(text)
        self.window.action_area.pack_start(label, True, True, 5)

        self.progressbar = gtk.ProgressBar()
        self.progressbar.set_pulse_step(0.1)
        self.window.action_area.pack_start(self.progressbar, True, True, 5)

        self.start = None

    def show(self):
        self.window.show_all()

    def destroy(self):
        self.window.destroy()

    def update(self, fraction):
        if self.start is None:
            self.start = time.time()

        if fraction is None:
            self.progressbar.set_text("")
            self.progressbar.pulse()
            return

        if fraction < 0.0: fraction = 0.0
        if fraction > 1.0: fraction = 1.0
            
        remaining = "Unknown"
        delta = time.time() - self.start
        if delta:
            rate = fraction / delta
            if rate:
                remaining = datetime.timedelta(seconds=int(round((1-fraction) / rate)))

        self.progressbar.set_text("%d%% (%s left)" % (fraction*100, remaining))
        self.progressbar.set_fraction(fraction)

