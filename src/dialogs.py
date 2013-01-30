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

class NewFolderDialog:
    def __init__(self, parent, callback):
        self.callback = callback

        self.window = gtk.Dialog(title="New folder", 
                                 parent=parent, 
                                 flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("Enter new folder name:")
        self.window.action_area.pack_start(label, True, True, 5)

        self.entry = gtk.Entry()
        self.entry.connect("activate", self.on_entry_activate)
        self.window.action_area.pack_start(self.entry, True, True, 5)

    def on_entry_activate(self, entry):
        text = entry.get_text()
        if text:
            gtk.Widget.destroy(self.window)
            self.callback(text)

    def run(self):
        self.window.show_all()

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
            
        rate = fraction / (time.time() - self.start)

        if rate:
            remaining = datetime.timedelta(seconds=int(round((1-fraction) / rate)))
        else:
            remaining = "Unknown"

        self.progressbar.set_text("%d%% (%s left)" % (fraction*100, remaining))
        self.progressbar.set_fraction(fraction)

