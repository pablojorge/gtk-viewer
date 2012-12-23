import os
import signal

import gtk

from filefactory import FileFactory

from imagefile import Size
from filemanager import Action, FileManager
from dialogs import (OpenDialog, InfoDialog, QuestionDialog, HelpDialog,
                     FileSelectorDialog, BasedirSelectorDialog, TargetSelectorDialog, 
                     RenameDialog)
from imageviewer import ImageViewer, ThumbnailViewer

from filescanner import get_files_from_args
from utils import get_process_memory_usage

class AutoScrolledWindow:
    def __init__(self, child, bg_color, on_special_drag_left, 
                                        on_special_drag_right, 
                                        on_scroll_event, 
                                        on_size_allocate):
        self.scrolled = gtk.ScrolledWindow()
        self.scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.connect("size-allocate", on_size_allocate)

        self.scrolled.add_with_viewport(child)
        viewport = child.get_parent()

        self.on_special_drag_left = on_special_drag_left
        self.on_special_drag_right = on_special_drag_right

        viewport.connect("scroll-event", self.on_scroll_event, on_scroll_event)
        viewport.connect("button-press-event", self.on_button_press_event)
        viewport.connect("button-release-event", self.on_button_release_event)
        viewport.connect("motion-notify-event", self.on_motion_notify_event)

        viewport.set_events(gtk.gdk.EXPOSURE_MASK | 
                            gtk.gdk.LEAVE_NOTIFY_MASK | 
                            gtk.gdk.BUTTON_PRESS_MASK | 
                            gtk.gdk.BUTTON_RELEASE_MASK | 
                            gtk.gdk.POINTER_MOTION_MASK | 
                            gtk.gdk.POINTER_MOTION_HINT_MASK)

        viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(bg_color))

    def get_widget(self):
        return self.scrolled

    def on_button_press_event(self, widget, event):
        if event.button == 1: # left
            widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

        self.prev_x = event.x_root
        self.prev_y = event.y_root

    def on_button_release_event(self, widget, event):
        if event.button == 1:
            widget.window.set_cursor(None)
        elif event.button == 3:
            offset = self.prev_x - event.x_root
            if offset < 0:
                self.on_special_drag_left()
            elif offset >= 0:
                self.on_special_drag_right()

    def on_motion_notify_event(self, widget, event):
        if not event.state & gtk.gdk.BUTTON1_MASK:
            return

        offset_x = self.prev_x - event.x_root
        offset_y = self.prev_y - event.y_root

        self.prev_x = event.x_root
        self.prev_y = event.y_root

        x_adj = widget.get_hadjustment()
        y_adj = widget.get_vadjustment() 

        new_x = x_adj.get_value() + offset_x
        new_y = y_adj.get_value() + offset_y

        if (new_x >= x_adj.get_lower() and 
            new_x <= (x_adj.get_upper() - x_adj.get_page_size())):
            x_adj.set_value(new_x)

        if (new_y >= y_adj.get_lower() and 
            new_y <= (y_adj.get_upper() - y_adj.get_page_size())):
            y_adj.set_value(new_y)

    def on_scroll_event(self, widget, event, callback):
        # to prevent partial re-drawings:
        widget.get_window().freeze_updates()

        # get full img size before and after zoom:
        old_size, new_size = callback(widget, event)

        # calculate the offset off the pointer inside the viewport:
        win_root = widget.get_window().get_origin()
        event_root = event.get_root_coords()

        event_x = event_root[0] - win_root[0]
        event_y = event_root[1] - win_root[1]

        # calculate the proportional location of the pointer inside the img:
        x_adj = widget.get_hadjustment()
        y_adj = widget.get_vadjustment() 

        px = (x_adj.get_value() + event_x) / old_size[0]
        py = (y_adj.get_value() + event_y) / old_size[1]

        # adjust the scrollbars to maintain the same position of the cursor:
        new_x = px * new_size[0] - event_x
        new_y = py * new_size[1] - event_y

        x_adj.set_value(new_x)
        y_adj.set_value(new_y)

        # re-enable updates:
        widget.get_window().thaw_updates()

        return True # to prevent further processing

class WidgetFactory:
    def __init__(self):
        pass

    def get_window(self, width, height, on_destroy, on_key_press_event):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_default_size(width, height)
        window.connect("destroy", on_destroy)
        window.connect("key_press_event", on_key_press_event)
        window.set_position(gtk.WIN_POS_CENTER)
        return window

    def get_image_from_stock(self, stock_id, size):
        image = gtk.Image()
        image.set_from_stock(stock_id, size)
        return image

    def get_event_box(self, child, bg_color, on_button_press_event, on_scroll_event):
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", on_button_press_event)
        ebox.connect("scroll-event", on_scroll_event)
        ebox.add(child)

        if bg_color:
            color = gtk.gdk.color_parse(bg_color)
            ebox.modify_bg(gtk.STATE_NORMAL, color)

        return ebox

class Pinbar:
    THUMB_COUNT = 10

    def __init__(self, main_app):
        self.main_app = main_app

        self.hidden = False
        self.pinbar_size = None
        self.thumb_array = []
        self.target_array = []

        factory = WidgetFactory()

        # Pinbar hbox
        self.hbox = gtk.HBox(True, 0)
        self.hbox.connect("size-allocate", self.on_size_allocate)

        for i in range(self.THUMB_COUNT):
            tvbox = gtk.VBox(False, 0)
            self.hbox.pack_start(tvbox, False, False, 1)

            th = ThumbnailViewer(1)
            self.thumb_array.append(th)
            self.target_array.append(None)
            th.fill()

            ebox = factory.get_event_box(child=th.get_widget(),
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, True, False, 0)
            
            label = gtk.Label()
            label.set_markup("<span underline='single'>%s</span>" % ((i+1) % self.THUMB_COUNT))

            ebox = factory.get_event_box(child=label,
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, False, False, 1)

    def on_size_allocate(self, widget, event, data=None):
        allocation = self.hbox.allocation
        width, height = allocation.width, allocation.height

        if self.pinbar_size != (width, height):
            self.pinbar_size = (width, height)

            for thumb in self.thumb_array:
                thumb.set_size((width-(self.THUMB_COUNT+1)) / self.THUMB_COUNT)

    def on_th_press(self, index):
        def handler(widget, event, data=None):
            if event.button == 1:
                self.send_to_target(index)
            else:
                self.associate_target(index)

        return handler

    def on_key_press(self, index):
        def handler():
            self.send_to_target(index)
        return handler

    def send_to_target(self, index):
        target = self.target_array[index]

        if not target:
            self.associate_target(index)
            target = self.target_array[index]
            if not target:
                return

        self.main_app.move_current(target)

    def associate_target(self, index):
        def on_file_selected(selection):
            imgfile = FileFactory.create(selection)
            dirname = imgfile.get_dirname()

            thumb = self.thumb_array[index]
            thumb.load(imgfile)
            thumb.set_tooltip_text(dirname)

            self.target_array[index] = dirname

        FileSelectorDialog("Select target dir", 
                           self.main_app.get_base_dir(),
                           None, 
                           on_file_selected).run()

    def get_widget(self):
        return self.hbox

    def hide(self):
        self.hidden = True
        self.get_widget().hide()

    def show(self):
        self.hidden = False
        self.get_widget().show()

    def toggle_visible(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

    def is_active(self):
        return self.hidden != True

class ViewerApp:
    DEF_WIDTH = 640
    DEF_HEIGHT = 480
    TH_SIZE = 200
    BG_COLOR = "#000000"

    def __init__(self, files, start_file, base_dir=None):
        ### Data definition
        self.file_manager = FileManager(self.on_list_empty,
                                        self.on_list_modified)

        self.files_order = None
        self.base_dir = base_dir
        self.last_opened_file = None
        self.last_targets = []
        self.undo_stack = []

        self.embedded_app = None
        self.fullscreen = False

        ### Window composition
        factory = WidgetFactory()

        self.window = factory.get_window(width=self.DEF_WIDTH, 
                                         height=self.DEF_HEIGHT,
                                         on_destroy=self.on_destroy,
                                         on_key_press_event=self.on_key_press_event)

        # Main vbox of the window (contains pinbar hbox, viewer hbox and status bar hbox)
        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

        self.pinbar = Pinbar(self)
        vbox.pack_start(self.pinbar.get_widget(), False, False, 0)

        # Viewer hbox
        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, True, True, 0)

        # Left thumbnail
        go_back = factory.get_image_from_stock(gtk.STOCK_GO_BACK, 1)
        ebox = factory.get_event_box(child=go_back,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_prev_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        self.th_left = ThumbnailViewer(self.TH_SIZE)
        ebox = factory.get_event_box(child=self.th_left.get_widget(),
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_prev_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Main viewer
        self.image_viewer = ImageViewer() 
        self.scrolled_size = None
        self.scrolled = AutoScrolledWindow(child=self.image_viewer.get_widget(),
                                           bg_color=self.BG_COLOR,
                                           on_special_drag_left=self.on_viewer_drag_left,
                                           on_special_drag_right=self.on_viewer_drag_right,
                                           on_scroll_event=self.on_viewer_scroll,
                                           on_size_allocate=self.on_viewer_size_allocate)
        hbox.pack_start(self.scrolled.get_widget(), True, True, 0)

        # Right thumbnail
        self.th_right = ThumbnailViewer(self.TH_SIZE)
        ebox = factory.get_event_box(child=self.th_right.get_widget(),
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        go_forward = factory.get_image_from_stock(gtk.STOCK_GO_FORWARD, 1)
        ebox = factory.get_event_box(child=go_forward,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Status Bar:
        self.status_bar = gtk.HBox(False, 0)
        vbox.pack_start(self.status_bar, False, False, 5)

        self.file_info = gtk.Label()
        self.memory_info = gtk.Label()
        self.additional_info = gtk.Label()
        self.file_index = gtk.Label()

        self.status_bar.pack_start(self.file_info, False, False, 10)
        self.status_bar.pack_start(self.memory_info, False, False, 10)
        self.status_bar.pack_start(self.additional_info, False, False, 10)

        self.status_bar.pack_end(self.file_index, False, False, 10)

        # Window composition end

        if files:
            self.set_files(files, start_file)
        else:
            open_dialog = OpenDialog(initial_dir=".", 
                                     callback=self.on_file_selected)
            open_dialog.run()

            if self.file_manager.empty():
                raise Exception("No files selected!")

        # Show main window AFTER obtaining file list
        self.window.show_all()

        # But start hiding the pinbar
        self.pinbar.hide()

    def set_files(self, files, start_file):
        self.file_manager.set_files(files)

        self.files_order = None
        self.undo_stack = []

        if start_file:
            self.file_manager.go_file(start_file)

        self.reload_viewer()

    ## Gtk event handlers
    def on_destroy(self, widget):
        gtk.main_quit()

    def on_key_press_event(self, widget, event, data=None):
        key_name = gtk.gdk.keyval_name(event.keyval)
        #print "key pressed:", key_name

        bindings = self.get_key_bindings()

        if key_name in bindings:
            bindings[key_name]()

    def on_viewer_size_allocate(self, widget, event, data=None):
        self.fit_viewer()
        self.refresh_info()

    def on_th_prev_press(self, widget, event, data=None):
        self.prev_image()

    def on_th_next_press(self, widget, event, data=None):
        self.next_image()

    def on_th_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            self.prev_image()
        else:
            self.next_image()

    # not real gtk events:
    def on_viewer_drag_left(self): self.prev_image()
    def on_viewer_drag_right(self): self.next_image()

    def on_viewer_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            factor = 1.05
        else:
            factor = 0.95

        old_size = self.image_viewer.get_scaled_size()

        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * factor)
        self.refresh_info()

        new_size = self.image_viewer.get_scaled_size()

        return old_size, new_size
    ##

    ## Internal callbacks
    def on_target_selected(self, target):
        self.move_current(target)

    def on_base_dir_selected(self, base_dir):
        self.base_dir = base_dir
        self.refresh_info()

    def on_file_selected(self, filename):
        self.last_opened_file = filename
        files, start_file = get_files_from_args([filename])
        self.set_files(files, start_file)

    def on_new_name_selected(self, new_name):
        if os.path.isfile(new_name):
            InfoDialog(self.window, "'%s' already exists!" % new_name).run()
            return

        self.undo_stack.append(self.file_manager.rename_current(new_name))

    def on_list_empty(self):
        if QuestionDialog(self.window, "No more files, select new one?").run():
            initial_dir = None
            if self.last_opened_file:
                initial_dir = os.path.dirname(self.last_opened_file)
            open_dialog = OpenDialog(initial_dir=initial_dir, 
                                     callback=self.on_file_selected)
            open_dialog.run()
        else:
            InfoDialog(self.window, "No more files, exiting").run()
            self.quit_app()

    def on_list_modified(self):
        self.reload_viewer()
    ## 

    ## Internal helpers
    def move_current(self, target_dir):
        if target_dir in self.last_targets:
            self.last_targets.remove(target_dir)

        self.last_targets.insert(0, target_dir)

        self.undo_stack.append(self.file_manager.move_current(target_dir))

    def stop_embedded_app(self):
        if self.embedded_app:
            os.kill(self.embedded_app, signal.SIGTERM)
            self.embedded_app = None

    def reload_viewer(self, force_stop=True):
        if force_stop:
            self.stop_embedded_app()
        self.image_viewer.load(self.file_manager.get_current_file())
        self.th_left.load(self.file_manager.get_prev_file())
        self.th_right.load(self.file_manager.get_next_file())

        self.fit_viewer(force=True)
        self.refresh_info()

    def fit_viewer(self, force=False):
        allocation = self.scrolled.get_widget().allocation
        width, height = allocation.width, allocation.height
        # Only redraw if size changed:
        if (width, height) != self.scrolled_size or force:
            self.image_viewer.zoom_at_size(width, height)
            self.scrolled_size = (width, height)

    def refresh_info(self):
        self.refresh_title()
        self.refresh_status()

    def refresh_title(self):
        image_file = self.file_manager.get_current_file()
        self.window.set_title(image_file.get_filename())

    def refresh_status(self):
        image_file = self.file_manager.get_current_file()

        # Markup reference:
        # http://www.gtk.org/api/2.6/pango/PangoMarkupFormat.html

        self.file_info.set_markup("<i>Date:</i> %s\n<i>Size:</i> %s pixels | %s | %d%%\n<i>SHA1:</i> %s" % \
                                  (image_file.get_mtime(),
                                   image_file.get_dimensions(),
                                   image_file.get_filesize(), 
                                   self.image_viewer.get_zoom_factor(),
                                   image_file.get_sha1()))

        rss, vsize = get_process_memory_usage()
        self.memory_info.set_markup("<i>RSS:</i> %s\n<i>VSize:</i> %s" % (Size(rss), Size(vsize)))

        additional = "<i>Base directory:</i> <b>%s</b>" % self.base_dir

        if self.last_targets:
            additional += "\n<i>Last directory:</i> <b>%s</b>" % self.last_targets[0]

        if self.undo_stack:
            last_action = self.undo_stack[-1]
            background, foreground = {
                Action.NORMAL : ("green", None),
                Action.WARNING : ("yellow", None),
                Action.DANGER : ("red", "white")
            }[last_action.severity]
            span = "<span"
            if background: span += " background='%s'" % background
            if foreground: span += " foreground='%s'" % foreground
            span += ">%s</span>" % last_action.description
            additional += "\n<i>Last action:</i> " + span

        self.additional_info.set_markup("%s" % additional)

        self.file_index.set_markup("<b><big>%d/%d</big></b>\n<i>Order:</i> %s" % \
                                   (self.file_manager.get_current_index() + 1, 
                                    self.file_manager.get_list_length(),
                                    self.files_order))
        self.file_index.set_justify(gtk.JUSTIFY_RIGHT)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        bindings = {
            ## Generic actions:
            "q"           : self.quit_app,
            "Escape"      : self.quit_app,
            "F1"          : self.show_help,
            "p"           : self.toggle_pinbar,
            "F11"         : self.toggle_fullscreen,
            "F12"         : self.toggle_thumbnails,

            ## Files navigation:
            "Home"        : self.first_image,
            "End"         : self.last_image,
            "Page_Down"   : self.jump_forward,
            "Page_Up"     : self.jump_backward,
            "space"       : self.next_image,
            "Right"       : self.next_image,
            "BackSpace"   : self.prev_image,
            "Left"        : self.prev_image,

            ## Files manipulation:
            "Down"        : self.show_selector,
            "Tab"         : self.show_selector,
            "l"           : self.show_selector,
            "o"           : self.open_file,
            "F2"          : self.rename_current,
            "F3"          : self.select_base_dir,
            "period"      : self.repeat_selection,
            "Return"      : self.repeat_selection,
            "u"           : self.undo_last,
            "z"           : self.undo_last,
            "s"           : self.toggle_star,
            "Delete"      : self.delete_image,
            "k"           : self.delete_image,
            "d"           : self.sort_by_date_asc,
            "D"           : self.sort_by_date_desc,
            "n"           : self.sort_by_name_asc,
            "N"           : self.sort_by_name_desc,
            "x"           : self.external_open,
            "e"           : self.embedded_open,

            ## Image manipulation:
            "1"           : self.zoom_100,
            "0"           : self.zoom_fit,
            "r"           : self.rotate_c,
            "R"           : self.rotate_cc,
            "f"           : self.flip_horizontal,
            "F"           : self.flip_vertical,
        }

        if self.fullscreen:
            bindings["Escape"] = self.toggle_fullscreen

        if self.pinbar.is_active():
            pinbar_bindings = {}

            for i in range(Pinbar.THUMB_COUNT):
                pinbar_bindings[str((i+1) % Pinbar.THUMB_COUNT)] = self.pinbar.on_key_press(i)

            bindings.update(pinbar_bindings)

        return bindings

    ## action handlers
    def quit_app(self):
        self.stop_embedded_app()
        gtk.Widget.destroy(self.window)

    def show_help(self):
        helpd = HelpDialog(self.window, self.get_key_bindings())
        helpd.show()

    def toggle_fullscreen(self):
        if not self.fullscreen:
            self.window.fullscreen()
            self.status_bar.hide()
            self.fullscreen = True
        else:
            self.window.unfullscreen()
            self.status_bar.show()
            self.fullscreen = False

    def toggle_thumbnails(self):
        self.th_left.toggle_visible()
        self.th_right.toggle_visible()

    def toggle_pinbar(self):
        self.pinbar.toggle_visible()

    def first_image(self):
        self.file_manager.go_first()

    def last_image(self):
        self.file_manager.go_last()

    def jump_forward(self):
        self.file_manager.go_forward(10)

    def jump_backward(self):
        self.file_manager.go_backward(10)

    def next_image(self):
        self.file_manager.go_forward(1)

    def prev_image(self):
        self.file_manager.go_backward(1)

    def get_base_dir(self):
        if self.base_dir:
            return self.base_dir
        else:
            return self.file_manager.get_current_file().get_dirname()

    def show_selector(self):
        selector = TargetSelectorDialog(initial_dir=self.get_base_dir(), 
                                        last_targets=self.last_targets, 
                                        callback=self.on_target_selected)
        selector.run()

    def open_file(self):
        initial_dir = self.file_manager.get_current_file().get_dirname()
        open_dialog = OpenDialog(initial_dir, self.on_file_selected)
        open_dialog.run()

    def rename_current(self):
        filename = self.file_manager.get_current_file().get_filename()
        renamer = RenameDialog(filename, self.on_new_name_selected)
        renamer.run()

    def select_base_dir(self):
        selector = BasedirSelectorDialog(initial_dir=self.get_base_dir(), 
                                         last_targets=[], 
                                         callback=self.on_base_dir_selected)
        selector.run()

    def repeat_selection(self):
        if not self.last_targets:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.move_current(self.last_targets[0])

    def undo_last(self):
        if not self.undo_stack:
            InfoDialog(self.window, "Nothing to undo!").run()
            return

        action = self.undo_stack.pop()
        action.undo()

    def toggle_star(self):
        self.undo_stack.append(self.file_manager.toggle_star())

    def delete_image(self):
        self.undo_stack.append(self.file_manager.delete_current())

    def sort_by_date_asc(self):
        self.files_order = "Date Asc"
        self.file_manager.sort_by_date(reverse=False)

    def sort_by_date_desc(self):
        self.files_order = "Date Desc"
        self.file_manager.sort_by_date(reverse=True)

    def sort_by_name_asc(self):
        self.files_order = "Name Asc"
        self.file_manager.sort_by_name(reverse=False)

    def sort_by_name_desc(self):
        self.files_order = "Name Desc"
        self.file_manager.sort_by_name(reverse=True)

    def external_open(self):
        current_file = self.file_manager.get_current_file()
        current_file.external_open()

    def embedded_open(self):
        current_file = self.file_manager.get_current_file()
        if self.embedded_app:
            self.reload_viewer(force_stop=True)
        else:
            self.embedded_app = current_file.embedded_open(self.window.get_window().xid)
            self.reload_viewer(force_stop=False)

    def zoom_100(self):
        self.image_viewer.zoom_at(100)
        self.refresh_info()

    def zoom_fit(self):
        self.fit_viewer(force=True)
        self.refresh_info()

    def rotate_c(self):
        self.image_viewer.rotate_c()

    def rotate_cc(self):
        self.image_viewer.rotate_cc()

    def flip_horizontal(self):
        self.image_viewer.flip_horizontal()

    def flip_vertical(self):
        self.image_viewer.flip_vertical()

    ##

    def run(self):
        gtk.main()

