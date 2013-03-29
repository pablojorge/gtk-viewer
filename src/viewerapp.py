import os
import sys
import string
import tempfile
import shutil
import cgi

import gtk

from imagefile import Size, GTKIconImage
from filemanager import Action, FileManager
from gallery import GalleryViewer
from chooser import (OpenDialog, BasedirSelectorDialog, TargetSelectorDialog, 
                     RenameDialog, DirectorySelectorDialog, OutputDialog)
from dialogs import (InfoDialog, ErrorDialog, AboutDialog, TextEntryDialog, 
                     QuestionDialog, ProgressBarDialog, TabbedInfoDialog)
from imageviewer import ImageViewer, ThumbnailViewer
from thumbnail import DirectoryThumbnail
from downloader import MultiDownloader

from archivefile import ArchiveGenerator
from giffile import GIFGenerator
from pdffile import PDFGenerator

from filescanner import FileFilter, FileScanner
from system import get_process_memory_usage, execute

from threads import Worker, Updater

class BlockedWidget:
    def __init__(self, widget, handler_id):
        self.widget = widget
        self.handler_id = handler_id

    def __enter__(self):
        self.widget.handler_block(self.handler_id)
        return self.widget

    def __exit__(self, *tb_info):
        self.widget.handler_unblock(self.handler_id)

class WidgetManager:
    def __init__(self):
        self.widget_dict = {}

    def add_widget(self, key, widget, handler_id):
        self.widget_dict[key] = widget
        self.widget_dict[key + "_handler"] = handler_id

    def get(self, key):
        return self.widget_dict[key]

    def get_blocked(self, key):
        return BlockedWidget(self.widget_dict[key],
                             self.widget_dict[key + "_handler"])

    def apply_blocked(self, key, action):
        with self.get_blocked(key) as blocked:
            action(blocked)

    def set_active(self, key, value):
        self.apply_blocked(key, lambda widget: widget.set_active(value))

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

    def get_menu(self, menu, widget_manager, accel_group):
        gmenu = gtk.Menu()
        gitem = gtk.MenuItem(menu["text"])
        gitem.set_submenu(gmenu)

        for item in menu["items"]:
            # Create menu item depending on type:
            if item.has_key("menu"):
                mitem = self.get_menu(item["menu"], widget_manager, accel_group)
            elif item.has_key("text"):
                mitem = gtk.MenuItem(item["text"])
            elif item.has_key("stock"):
                mitem = gtk.ImageMenuItem(item["stock"], accel_group)
            elif item.has_key("separator"):
                mitem = gtk.SeparatorMenuItem()
            elif item.has_key("toggle"):
                mitem = gtk.CheckMenuItem(item["toggle"])
                if item.has_key("active") and item["active"]:
                    mitem.set_active(True)

            if item.has_key("accel"):
                accel = item["accel"]
                if type(accel) is str:
                    key, mod = gtk.accelerator_parse(item["accel"])
                else:
                    key, mod = accel
                mitem.add_accelerator("activate", accel_group, key, mod, gtk.ACCEL_VISIBLE)

            if item.has_key("sensitive"):
                mitem.set_sensitive(item["sensitive"])

            # Connect handler if available:
            if item.has_key("handler"):
                handler_id = mitem.connect("activate", item["handler"])
            else:
                handler_id = None

            if item.has_key("key"):
                widget_manager.add_widget(item["key"], mitem, handler_id)

            # Add it to the menu:
            gmenu.append(mitem)
        
        return gitem

    def get_menu_bar(self, accel_group, widget_manager, menus):
        menu_bar = gtk.MenuBar()

        for menu in menus:
            menu_bar.append(self.get_menu(menu, widget_manager, accel_group))

        return menu_bar

class Pinbar:
    THUMB_COUNT = 10

    def __init__(self, main_app, default_width):
        self.main_app = main_app

        self.active = True
        self.auto = False
        self.pinbar_size = None
        self.thumb_array = []
        self.target_array = []
        self.label_array = []

        factory = WidgetFactory()

        # Pinbar hbox
        self.hbox = gtk.HBox(True, 0)
        self.hbox.connect("size-allocate", self.on_size_allocate)

        for i in range(self.THUMB_COUNT):
            tvbox = gtk.VBox(False, 0)
            self.hbox.pack_start(tvbox, False, False, 1)

            th = ThumbnailViewer(self.get_thumb_width(default_width))
            self.thumb_array.append(th)
            self.target_array.append(None)
            th.fill()

            ebox = factory.get_event_box(child=th.get_widget(),
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, True, False, 0)
            
            label = gtk.Label()
            label.set_size_request(self.get_thumb_width(default_width), -1)
            self.label_array.append(label)

            ebox = factory.get_event_box(child=label,
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, False, False, 1)

        self.reset_targets()

    def get_thumb_width(self, width):
        return (width-(self.THUMB_COUNT+1)) / self.THUMB_COUNT

    def on_size_allocate(self, widget, event, data=None):
        allocation = widget.allocation
        width, height = allocation.width, allocation.height

        if self.pinbar_size != (width, height):
            self.pinbar_size = (width, height)

            for thumb in self.thumb_array:
                thumb.set_size(self.get_thumb_width(width))

    def on_th_press(self, index):
        def handler(widget, event, data=None):
            if event.button == 1:
                self.send_to_target(index)
            else:
                self.associate_target(index)

        return handler

    def on_send_to(self, index):
        def handler(_):
            if self.is_active():
                self.send_to_target(index)
        return handler

    def on_associate(self, index):
        def handler(_):
            if self.is_active():
                self.associate_target(index)
        return handler

    def on_reset(self, _):
        if self.is_active():
            self.reset_targets()

    def on_auto_associate(self, toggle):
        self.auto = toggle.get_active()

    def on_targets_updated(self, target_list):
        if self.is_active() and self.auto:
            for index in range(0, min(len(target_list), self.THUMB_COUNT)):
                target = target_list[index]
                thumbnail = DirectoryThumbnail(target)
                self.set_target(index, thumbnail, target)
            for index in range(len(target_list), self.THUMB_COUNT):
                self.reset_target(index)

    def on_multi_associate(self, _):
        def on_dir_selected(selection):
            scanner = FileScanner()
            dirs = scanner.get_dirs_from_dir(selection)

            if len(dirs) > self.THUMB_COUNT:
                InfoDialog(self.main_app.window,
                           "Too many categories in %s (%d, maximum allowed: %d)" \
                            % (selection, len(dirs), self.THUMB_COUNT)).run()
                return

            self.reset_targets()

            for index, dirname in enumerate(dirs):
                thumbnail = DirectoryThumbnail(dirname)
                self.set_target(index, thumbnail, dirname)

        if self.is_active():
            DirectorySelectorDialog("Select directory containing categories", 
                                    self.main_app.window,
                                    self.main_app.get_base_dir(),
                                    self.main_app.last_targets, 
                                    on_dir_selected).run()

    def refresh_buckets(self):
        if self.is_active():
            for index in range(self.THUMB_COUNT):
                thumb = self.thumb_array[index]
                thumb.redraw()

    def send_to_target(self, index):
        target = self.target_array[index]

        if not target:
            self.associate_target(index)
        else:
            self.main_app.move_current(target)

    def associate_target(self, index):
        def on_dir_selected(selection):
            thumbnail = DirectoryThumbnail(selection)
            self.set_target(index, thumbnail, selection)

        DirectorySelectorDialog("Select target directory for bucket %i" % (index+1), 
                                self.main_app.window,
                                self.main_app.get_base_dir(),
                                self.main_app.last_targets, 
                                on_dir_selected).run()

    def reset_target(self, index):
        self.set_target(index, GTKIconImage(gtk.STOCK_DIALOG_QUESTION, 128), None) 

    def reset_targets(self):
        for i in range(self.THUMB_COUNT):
            self.reset_target(i)

    def set_target(self, index, imgfile, dirname):
        thumb = self.thumb_array[index]

        if imgfile:
            thumb.load(imgfile)
        else:
            thumb.reset()

        thumb.set_tooltip_text(dirname)

        self.target_array[index] = dirname

        label = "<span underline='single'>%s</span>" % ((index+1) % self.THUMB_COUNT)

        if dirname:
            label += " %s" % os.path.split(dirname)[-1]

        self.label_array[index].set_markup(label)

    def get_widget(self):
        return self.hbox

    def hide(self):
        self.active = False
        self.get_widget().hide()

    def show(self):
        self.active = True
        self.get_widget().show()

    def is_active(self):
        return self.active

class UndoStack:
    def __init__(self, on_push, on_stack_empty):
        self.stack = []
        self.on_push = on_push
        self.on_stack_empty = on_stack_empty

    def clear(self):
        self.stack = []
        self.on_stack_empty()

    def push(self, action):
        if not action:
            return
        self.stack.append(action)
        self.on_push(action)

    def empty(self):
        return not self.stack

    def top(self): 
        return self.stack[-1]

    def pop(self):
        action = self.stack.pop()
        if self.empty():
            self.on_stack_empty()
        return action

class ViewerApp:
    DEF_WIDTH = 1200
    DEF_HEIGHT = 768
    TH_SIZE = 200
    BG_COLOR = "#000000"

    def __init__(self, files, start_file, base_dir=None):
        ### Data definition
        self.file_manager = FileManager(self.on_list_modified)

        self.files_order = None
        self.base_dir = base_dir
        self.last_targets = []
        self.undo_stack = UndoStack(self.on_undo_stack_push, 
                                    self.on_undo_stack_empty)
        self.filter_ = FileFilter()

        self.fullview_active = False

        ### Window composition
        factory = WidgetFactory()
        self.widget_manager = WidgetManager()

        self.window = factory.get_window(width=self.DEF_WIDTH, 
                                         height=self.DEF_HEIGHT,
                                         on_destroy=self.on_destroy,
                                         on_key_press_event=self.on_key_press_event)

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        # Main vbox of the window (contains pinbar hbox, viewer hbox and status bar hbox)
        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

        # Must be instatiated first to associate the accelerators:
        self.pinbar = Pinbar(self, self.DEF_WIDTH)

        # Menubar
        menus = self.get_menubar_entries(self.pinbar)
        self.menu_bar = factory.get_menu_bar(self.accel_group, self.widget_manager, menus)
        vbox.pack_start(self.menu_bar, False, False, 0)

        self.load_icons() # load icons before creating toolbars

        # Toolbar
        self.toolbar = self.build_toolbar(self.widget_manager)
        vbox.pack_start(self.toolbar, False, False, 0)

        # Filter toolbar
        self.filterbar = self.build_filterbar(self.widget_manager)
        vbox.pack_start(self.filterbar, False, False, 0)

        # Pinbar (pack it AFTER the toolbars)
        vbox.pack_start(self.pinbar.get_widget(), False, False, 0)

        # Viewer hbox
        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, True, True, 0)

        # Left thumbnail
        self.go_back_icon = factory.get_image_from_stock(gtk.STOCK_GO_BACK, 1)
        ebox = factory.get_event_box(child=self.go_back_icon,
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

        self.go_forward_icon = factory.get_image_from_stock(gtk.STOCK_GO_FORWARD, 1)
        ebox = factory.get_event_box(child=self.go_forward_icon,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Name label
        self.file_name = gtk.Label()
        self.file_name.set_selectable(True)
        self.file_name.set_size_request(self.DEF_WIDTH, -1)
        ebox = factory.get_event_box(child=self.file_name,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=lambda: None,
                                     on_scroll_event=lambda: None)
        vbox.pack_start(ebox, False, False, 0)

        # Status Bar:
        self.status_bar = gtk.HBox(False, 0)
        vbox.pack_start(self.status_bar, False, False, 5)

        self.file_info = gtk.Label()
        self.status_bar.set_size_request(self.DEF_WIDTH, -1)
        self.file_index = gtk.Label()

        self.status_bar.pack_start(self.file_info, False, False, 10)
        self.status_bar.pack_end(self.file_index, False, False, 10)

        # Window composition end

        # Loaders pool:
        self.pool = []
        self.main_loader = Worker()
        self.loader_left = Worker()
        self.loader_right = Worker()
        self.pool.append(self.main_loader)
        self.pool.append(self.loader_left)
        self.pool.append(self.loader_right)

        for worker in self.pool:
            worker.start()

        # Initial set of files:
        self.set_files(files, start_file)

        # Show main window AFTER obtaining file list
        self.window.show_all()
        self.window.set_focus(None)
        # But initially hide the filter bar and pinbar
        self.filterbar.hide()
        self.pinbar.hide()

    def get_menubar_entries(self, pinbar):
        pinbar_send = lambda i: {"text" : "Bucket %i" % ((i+1)%10),
                                 "accel" : "%i" % ((i+1)%10),
                                 "handler" : pinbar.on_send_to(i)}
        pinbar_assoc = lambda i: {"text" : "Bucket %i" % ((i+1)%10),
                                  "accel" : "<Control>%i" % ((i+1)%10),
                                  "handler" : pinbar.on_associate(i)}

        return [{"text" : "_File",
                 "items" : [{"stock" : gtk.STOCK_OPEN,
                             "accel" : "O",
                             "handler" : self.on_open_file},
                            {"separator" : True},
                            {"text" : "Rename",
                             "accel" : "<Control>M",
                             "handler" : self.on_rename_current},
                            {"stock" : gtk.STOCK_DELETE,
                             "accel" : "K",
                             "handler" : self.on_delete_current},
                            {"separator" : True},
                            {"text" : "Mass download...",
                             "handler" : self.on_mass_download},
                            {"text" : "Mass delete...",
                             "handler" : self.on_mass_delete},
                            {"separator" : True},
                            {"text" : "Open in nautilus",
                             "handler" : self.on_open_in_nautilus},
                            {"stock" : gtk.STOCK_INFO,
                             "accel" : (gtk.keysyms.comma, 0),
                             "handler" : self.on_show_info},
                            {"text" : "Open in external viewer",
                             "accel" : "X",
                             "handler" : self.on_external_open},
                            {"text" : "Extract contents",
                             "accel" : "E",
                             "key" : "extract_mitem",
                             "handler" : self.on_extract_contents},
                            {"menu" : {"text" : "Generate ...",
                                       "items" : [{"text" : "Animated GIF from set",
                                                   "handler" : self.on_generate_gif},
                                                  {"text" : "Archive from set",
                                                   "handler" : self.on_generate_archive},
                                                  {"text" : "PDF from set",
                                                   "handler" : self.on_generate_pdf}]}},
                            {"toggle" : "Enable animation",
                             "accel" : "G",
                             "key" : "animation_toggle",
                             "handler" : self.on_enable_animation},
                            {"separator" : True},
                            {"stock" : gtk.STOCK_QUIT,
                             "accel" : "Q",
                             "handler" : self.on_quit_app}]},
                {"text" : "_Edit",
                 "items" : [{"stock" : gtk.STOCK_UNDO,
                             "accel" : "U",
                             "key" : "undo_mitem",
                             "sensitive" : False,
                             "handler" : self.on_undo},
                            {"separator" : True},
                            {"toggle" : "Star image",
                             "key" : "star_toggle",
                             "accel" : "S",
                             "handler" : self.on_toggle_star},
                            {"separator" : True},
                            {"text" : "Select base directory",
                             "accel" : "B",
                             "handler" : self.on_select_base_dir},
                            {"text" : "Copy to target",
                             "accel" : "Y",
                             "handler" : self.on_copy_to_target},
                            {"text" : "Move to target",
                             "accel" : "M",
                             "handler" : self.on_move_to_target},
                            {"text" : "Reuse last target",
                             "key" : "reuse_mitem",
                             "accel" : (gtk.keysyms.period, 0),
                             "handler" : self.on_reuse_target}]},
                {"text" : "_View",
                 "items" : [{"toggle" : "Show toolbar",
                             "active" : True,
                             "accel" : "A",
                             "key" : "toolbar_toggle",
                             "handler" : self.on_toggle_toolbar},
                            {"toggle" : "Show thumbnails",
                             "active" : True,
                             "accel" : "T",
                             "key" : "thumbnails_toggle",
                             "handler" : self.on_toggle_thumbnails},
                            {"toggle" : "Show status bar",
                             "active" : True,
                             "accel" : "C",
                             "key" : "status_bar_toggle",
                             "handler" : self.on_toggle_status_bar},
                            {"separator" : True},
                            {"toggle" : "Zoom to fit",
                             "active" : True,
                             "accel" : "Z",
                             "key" : "zoom_to_fit_toggle",
                             "handler" : self.on_toggle_zoom},
                            {"stock" : gtk.STOCK_ZOOM_IN,
                             "accel" : (gtk.keysyms.plus, 0),
                             "handler" : self.on_zoom_in},
                            {"stock" : gtk.STOCK_ZOOM_OUT,
                             "accel" : (gtk.keysyms.minus, 0),
                             "handler" : self.on_zoom_out},
                            {"separator" : True},
                            {"text" : "Gallery view",
                             "accel" : "W",
                             "handler" : self.on_gallery_view},
                            {"toggle" : "Fullscreen",
                             "accel" : "L",
                             "key" : "fullscreen_toggle",
                             "handler" : self.on_toggle_fullscreen}]},
                {"text" : "_Image",
                 "items" : [{"text" : "Rotate clockwise",
                             "accel" : "R",
                             "handler" : self.on_rotate_c},
                            {"text" : "Rotate counter-clockwise",
                             "accel" : "<Control>R",
                             "handler" : self.on_rotate_cc},
                            {"separator" : True},
                            {"text" : "Flip horizontal",
                             "accel" : "<Control>H",
                             "handler" : self.on_flip_horizontal},
                            {"text" : "Flip vertical",
                             "accel" : "<Control>F",
                             "handler" : self.on_flip_vertical}]},
                {"text" : "Fi_lter",
                 "items" : [{"toggle" : "Show filter bar",
                             "accel" : "F",
                             "key" : "filterbar_toggle",
                             "handler" : self.on_show_filterbar},
                            {"separator" : True},
                            {"toggle" : "Show images",
                             "key" : "filter_images_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"toggle" : "Show videos",
                             "key" : "filter_videos_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"toggle" : "Show GIF files",
                             "key" : "filter_gifs_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"toggle" : "Show PDFs",
                             "key" : "filter_pdfs_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"toggle" : "Show EPUBs",
                             "key" : "filter_epubs_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"toggle" : "Show Archives",
                             "key" : "filter_archives_toggle",
                             "active" : True,
                             "handler" : self.on_filetype_toggle},
                            {"text" : "Show all filetypes",
                             "handler" : self.on_show_all_filetypes},
                            {"text" : "Hide all filetypes",
                             "handler" : self.on_hide_all_filetypes},
                            {"separator" : True},
                            {"toggle" : "Show starreds",
                             "key" : "filter_starred_toggle",
                             "active" : True,
                             "handler" : self.on_status_toggle},
                            {"toggle" : "Show unstarreds",
                             "key" : "filter_unstarred_toggle",
                             "active" : True,
                             "handler" : self.on_status_toggle},
                            {"text" : "Show all statuses",
                             "handler" : self.on_show_all_status},
                            {"text" : "Hide all statuses",
                             "handler" : self.on_hide_all_status},
                            ]},
                {"text" : "_Go",
                 "items" : [{"stock" : gtk.STOCK_GOTO_FIRST,
                             "accel" : "H",
                             "handler" : self.on_goto_first},
                            {"stock" : gtk.STOCK_GOTO_LAST,
                             "accel" : "End",
                             "handler" : self.on_goto_last},
                            {"separator" : True},
                            {"stock" : gtk.STOCK_GO_FORWARD,
                             "accel" : "Right",
                             "handler" : self.on_go_forward},
                            {"stock" : gtk.STOCK_GO_BACK,
                             "accel" : "Left",
                             "handler" : self.on_go_back},
                            {"separator" : True},
                            {"text" : "Jump forward",
                             "accel" : "<Alt>Right",
                             "handler" : self.on_jump_forward},
                            {"stock" : "Jump back",
                             "accel" : "<Alt>Left",
                             "handler" : self.on_jump_back},
                            {"stock" : gtk.STOCK_JUMP_TO,
                             "accel" : "J",
                             "handler" : self.on_jump_to},
                            {"separator" : True},
                            {"menu" : {"text" : "Sort by ...",
                                       "items" : [{"toggle" : "Sort by name",
                                                   "accel" : "N",
                                                   "key" : "sort_by_name_toggle",
                                                   "handler" : self.on_sort_by_name},
                                                  {"toggle" : "Sort by date",
                                                   "accel" : "D",
                                                   "key" : "sort_by_date_toggle",
                                                   "handler" : self.on_sort_by_date},
                                                  {"toggle" : "Sort by size",
                                                   "key" : "sort_by_size_toggle",
                                                   "handler" : self.on_sort_by_size},
                                                  {"toggle" : "Sort by dimensions",
                                                   "key" : "sort_by_dimensions_toggle",
                                                   "handler" : self.on_sort_by_dimensions},
                                                  {"separator" : True},
                                                  {"toggle" : "Inverted order",
                                                   "key" : "inverted_order_toggle",
                                                   "sensitive" : False,
                                                   "accel" : "I",
                                                   "handler" : self.on_toggle_sort_order}]}}]},
                {"text" : "_Pinbar",
                 "items" : [{"toggle" : "Show pinbar",
                             "accel" : "P",
                             "key" : "pinbar_toggle",
                             "handler" : self.on_show_pinbar},
                            {"toggle" : "Auto-associate buckets",
                             "handler" : pinbar.on_auto_associate},
                            {"text" : "Associate all buckets",
                             "handler" : pinbar.on_multi_associate},
                            {"text" : "Reset all buckets",
                             "handler" : pinbar.on_reset},
                            {"separator" : True},
                            {"menu" : {"text" : "Send to",
                                       "items" : [pinbar_send(0), pinbar_send(1), 
                                                  pinbar_send(2), pinbar_send(3), 
                                                  pinbar_send(4), pinbar_send(5), 
                                                  pinbar_send(6), pinbar_send(7), 
                                                  pinbar_send(8), pinbar_send(9),]}},
                            {"menu" : {"text" : "Associate",
                                       "items" : [pinbar_assoc(0), pinbar_assoc(1), 
                                                  pinbar_assoc(2), pinbar_assoc(3), 
                                                  pinbar_assoc(4), pinbar_assoc(5), 
                                                  pinbar_assoc(6), pinbar_assoc(7), 
                                                  pinbar_assoc(8), pinbar_assoc(9)]}}]},
                {"text" : "_Help",
                 "items" : [{"text" : "See commands reference",
                             "accel" : (gtk.keysyms.question, 0),
                             "handler" : self.on_show_commands_reference},
                            {"separator" : True},
                            {"stock" : gtk.STOCK_ABOUT,
                             "handler" : self.on_show_about}]}]

    def build_toolbar(self, widget_manager):
        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)

        tooltips = gtk.Tooltips()
        toolbar.set_tooltips(True)
        
        button = gtk.ToolButton(gtk.STOCK_OPEN)
        button.connect("clicked", self.on_open_file)
        button.set_tooltip(tooltips, "Open")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_SAVE_AS)
        button.connect("clicked", self.on_rename_current)
        button.set_tooltip(tooltips, "Rename")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_DELETE)
        button.connect("clicked", self.on_delete_current)
        button.set_tooltip(tooltips, "Delete")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton(gtk.STOCK_UNDO)
        handler_id = button.connect("clicked", self.on_undo)
        button.set_tooltip(tooltips, "Undo")
        button.set_sensitive(False)
        widget_manager.add_widget("undo_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToggleToolButton(gtk.STOCK_ABOUT)
        handler_id = button.connect("clicked", self.on_toggle_star)
        button.set_tooltip(tooltips, "Star")
        widget_manager.add_widget("star_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_INDENT)
        button.connect("clicked", self.on_move_to_target)
        button.set_tooltip(tooltips, "Move")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_REFRESH)
        handler_id = button.connect("clicked", self.on_reuse_target)
        button.set_tooltip(tooltips, "Reuse")
        widget_manager.add_widget("reuse_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton(gtk.STOCK_INFO)
        button.connect("clicked", self.on_show_info)
        button.set_tooltip(tooltips, "Show information")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_EXECUTE)
        button.connect("clicked", self.on_external_open)
        button.set_tooltip(tooltips, "External open")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_CONVERT)
        handler_id = button.connect("clicked", self.on_extract_contents)
        button.set_tooltip(tooltips, "Extract contents")
        widget_manager.add_widget("extract_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton(gtk.STOCK_MEDIA_PLAY)
        handler_id = button.connect("clicked", self.on_enable_animation)
        button.set_tooltip(tooltips, "Enable animation")
        widget_manager.add_widget("animation_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToggleToolButton(gtk.STOCK_ZOOM_FIT)
        button.set_active(True)
        handler_id = button.connect("clicked", self.on_toggle_zoom)
        button.set_tooltip(tooltips, "Toggle zoom mode")
        widget_manager.add_widget("zoom_to_fit_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_ZOOM_IN)
        button.connect("clicked", self.on_zoom_in)
        button.set_tooltip(tooltips, "Zoom in")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_ZOOM_OUT)
        button.connect("clicked", self.on_zoom_out)
        button.set_tooltip(tooltips, "Zoom out")
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton(gtk.STOCK_FULLSCREEN)
        handler_id = button.connect("clicked", self.on_toggle_fullscreen)
        button.set_tooltip(tooltips, "Enable fullscreen")
        widget_manager.add_widget("fullscreen_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton("rotate-counter-clockwise")
        button.connect("clicked", self.on_rotate_cc)
        button.set_tooltip(tooltips, "Rotate counter-clockwise")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("rotate-clockwise")
        button.connect("clicked", self.on_rotate_c)
        button.set_tooltip(tooltips, "Rotate clockwise")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("flip-horizontal")
        button.connect("clicked", self.on_flip_horizontal)
        button.set_tooltip(tooltips, "Flip horizontal")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("flip-vertical")
        button.connect("clicked", self.on_flip_vertical)
        button.set_tooltip(tooltips, "Flip vertical")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToolButton(gtk.STOCK_GOTO_FIRST)
        button.connect("clicked", self.on_goto_first)
        button.set_tooltip(tooltips, "Go to first file")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GOTO_LAST)
        button.connect("clicked", self.on_goto_last)
        button.set_tooltip(tooltips, "Go to last file")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_MEDIA_REWIND)
        button.connect("clicked", self.on_jump_back)
        button.set_tooltip(tooltips, "Jump back")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_MEDIA_FORWARD)
        button.connect("clicked", self.on_jump_forward)
        button.set_tooltip(tooltips, "Jump forward")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_JUMP_TO)
        button.connect("clicked", self.on_jump_to)
        button.set_tooltip(tooltips, "Jump to")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GO_BACK)
        button.connect("clicked", self.on_go_back)
        button.set_tooltip(tooltips, "Previous")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GO_FORWARD)
        button.connect("clicked", self.on_go_forward)
        button.set_tooltip(tooltips, "Next")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToggleToolButton(gtk.STOCK_ITALIC)
        handler_id = button.connect("clicked", self.on_sort_by_name)
        button.set_tooltip(tooltips, "Sort by name")
        widget_manager.add_widget("sort_by_name_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton("sort-by-date")
        handler_id = button.connect("clicked", self.on_sort_by_date)
        button.set_tooltip(tooltips, "Sort by date")
        widget_manager.add_widget("sort_by_date_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton("sort-by-size")
        handler_id = button.connect("clicked", self.on_sort_by_size)
        button.set_tooltip(tooltips, "Sort by size")
        widget_manager.add_widget("sort_by_size_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton("sort-ascending")
        handler_id = button.connect("clicked", self.on_toggle_sort_order)
        button.set_tooltip(tooltips, "Toggle sort order")
        button.set_sensitive(False)
        widget_manager.add_widget("inverted_order_button", button, handler_id)
        toolbar.insert(button, -1)

        return toolbar

    def build_filterbar(self, widget_manager):
        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)

        tooltips = gtk.Tooltips()
        toolbar.set_tooltips(True)

        for stock_id, text, key in [("image-file", "Images", "images"),
                                    ("video-file", "Videos", "videos"),
                                    ("gif-file", "GIFs", "gifs"),
                                    ("pdf-file", "PDFs", "pdfs"),
                                    ("epub-file", "EPUBs", "epubs"),
                                    ("archive", "Archives", "archives")]:
            button = gtk.ToggleToolButton(stock_id)
            button.set_active(True)
            button.set_is_important(True)
            handler_id = button.connect("clicked", self.on_filetype_toggle)
            button.set_label(text)
            button.set_tooltip(tooltips, text)
            widget_manager.add_widget("filter_%s_button" % key, button, handler_id)
            toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_OK)
        button.set_is_important(True)
        button.set_label("All")
        handler_id = button.connect("clicked", self.on_show_all_filetypes)
        button.set_tooltip(tooltips, "Show all filetypes")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_CANCEL)
        button.set_is_important(True)
        button.set_label("None")
        handler_id = button.connect("clicked", self.on_hide_all_filetypes)
        button.set_tooltip(tooltips, "Hide all filetypes")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        for stock_id, text, key in [(gtk.STOCK_ABOUT, "Starreds", "starred"),
                                    ("unstarred", "Unstarreds", "unstarred")]:
            button = gtk.ToggleToolButton(stock_id)
            button.set_active(True)
            button.set_is_important(True)
            handler_id = button.connect("clicked", self.on_status_toggle)
            button.set_label(text)
            button.set_tooltip(tooltips, text)
            widget_manager.add_widget("filter_%s_button" % key, button, handler_id)
            toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_OK)
        button.set_is_important(True)
        button.set_label("All")
        handler_id = button.connect("clicked", self.on_show_all_status)
        button.set_tooltip(tooltips, "Show all statuses")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_CANCEL)
        button.set_is_important(True)
        button.set_label("None")
        handler_id = button.connect("clicked", self.on_hide_all_status)
        button.set_tooltip(tooltips, "Hide all statuses")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        item = gtk.ToolItem()
        entry = gtk.Entry()
        entry.connect("focus-in-event", self.on_filter_entry_focus_in)
        entry.connect("focus-out-event", self.on_filter_entry_focus_out)
        entry.connect("activate", self.on_filter_entry_activate)
        widget_manager.add_widget("filter_entry", entry, None)
        item.add(entry)
        toolbar.insert(item, -1)

        button = gtk.ToolButton(gtk.STOCK_CLEAR)
        handler_id = button.connect("clicked", self.on_filter_entry_clear)
        toolbar.insert(button, -1)

        return toolbar

    def load_icons(self):
        factory = gtk.IconFactory()

        icons = [("rotate-clockwise", "icons/rotate-clockwise.png"),
                 ("rotate-counter-clockwise", "icons/rotate-counter-clockwise.png"),
                 ("flip-horizontal", "icons/flip-horizontal.png"),
                 ("flip-vertical", "icons/flip-vertical.png"),
                 ("sort-by-date", "icons/sort-by-date.png"),
                 ("sort-by-size", "icons/sort-by-size.png"),
                 ("sort-ascending", "icons/sort-ascending.png"),
                 ("sort-descending", "icons/sort-descending.png"),
                 ("image-file", "icons/image-file.png"),
                 ("video-file", "icons/video-file.png"),
                 ("gif-file", "icons/gif-file.png"),
                 ("pdf-file", "icons/pdf-file.png"),
                 ("epub-file", "icons/epub-file.png"),
                 ("archive", "icons/archive.png"),
                 ("unstarred", "icons/unstarred.png")]

        root_path = os.path.split(os.path.dirname(__file__))[0]

        for icon_id, filename in icons:
            pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(root_path, filename))
            iconset = gtk.IconSet(pixbuf)
            factory.add(icon_id, iconset)

        factory.add_default()

    def set_files(self, files, start_file):
        self.file_manager.set_files(files)

        if start_file:
            self.file_manager.go_file(start_file)

        self.reload_viewer()

    def clear_filters(self):
        self.toggle_all_filetypes(True)
        self.toggle_all_status(True)

    def toggle_all_filetypes(self, value):
        for filetype in self.filter_.get_valid_filetypes():
            toggle_id = "filter_%s_toggle" % filetype
            button_id = "filter_%s_button" % filetype
            self.widget_manager.set_active(toggle_id, value)
            self.widget_manager.set_active(button_id, value)
            self.filter_.enable_filetype(filetype, value)

    def toggle_all_status(self, value):
        for status in self.filter_.get_valid_status():
            toggle_id = "filter_%s_toggle" % status
            button_id = "filter_%s_button" % status
            self.widget_manager.set_active(toggle_id, value)
            self.widget_manager.set_active(button_id, value)
            self.filter_.enable_status(status, value)

    ## Gtk event handlers
    def on_destroy(self, widget):
        for worker in self.pool:
            worker.stop()
            worker.join()
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
        self.on_go_back(None)

    def on_th_next_press(self, widget, event, data=None):
        self.on_go_forward(None)

    def on_th_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            self.on_go_back(None)
        else:
            self.on_go_forward(None)

    # not real gtk events:
    def on_viewer_drag_left(self): self.on_go_back(None)
    def on_viewer_drag_right(self): self.on_go_forward(None)

    def on_viewer_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            factor = 1.05
        else:
            factor = 0.95

        old_size = self.image_viewer.get_scaled_size()

        self.widget_manager.set_active("zoom_to_fit_toggle", False)
        self.widget_manager.set_active("zoom_to_fit_button", False)
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * factor)
        self.refresh_info()

        new_size = self.image_viewer.get_scaled_size()

        return old_size, new_size
    ##

    ## Internal callbacks
    def on_copy_target_selected(self, target):
        self.copy_current(target)

    def on_target_selected(self, target):
        self.move_current(target)

    def on_base_dir_selected(self, base_dir):
        self.base_dir = base_dir
        self.refresh_info()

    def on_file_selected(self, filename):
        self.clear_filters()
        self.last_targets = []
        scanner = FileScanner()
        files = scanner.get_files_from_filename(filename)
        self.undo_stack.clear()
        self.set_files(files, filename)

    def on_dir_selected(self, dirname, recursive):
        self.clear_filters()
        self.last_targets = []
        scanner = FileScanner(recursive=recursive)
        files, start_file = scanner.get_files_from_args([dirname])
        self.undo_stack.clear()
        self.set_files(files, start_file)

    def on_new_name_selected(self, new_name):
        if os.path.isfile(new_name):
            InfoDialog(self.window, "'%s' already exists!" % new_name).run()
            return

        self.undo_stack.push(self.file_manager.rename_current(new_name))

    def on_list_modified(self):
        self.reload_viewer()

    def on_undo_stack_push(self, item):
        self.widget_manager.get("undo_mitem").set_sensitive(True)
        self.widget_manager.get("undo_button").set_sensitive(True)

    def on_undo_stack_empty(self):
        self.widget_manager.get("undo_mitem").set_sensitive(False)
        self.widget_manager.get("undo_button").set_sensitive(False)
    ## 

    ## Internal helpers
    def update_target(self, target_dir):
        if target_dir in self.last_targets:
            self.last_targets.remove(target_dir)

        self.last_targets.insert(0, target_dir)
        self.pinbar.on_targets_updated(self.last_targets)

    def copy_current(self, target_dir):
        self.update_target(target_dir)
        self.undo_stack.push(self.file_manager.copy_current(target_dir))

    def move_current(self, target_dir):
        self.update_target(target_dir)
        self.undo_stack.push(self.file_manager.move_current(target_dir))

    def apply_filter(self):
        dialog = ProgressBarDialog(self.window, "Applying filter...")
        dialog.show()
        updater = Updater(self.file_manager.apply_filter(self.filter_),
                          dialog.update,
                          self.on_filter_applied,
                          (dialog,))
        updater.start()

    def on_filter_applied(self, dialog):
        try:
            dialog.destroy()
        finally:
            pass

    def reload_viewer(self):
        current_file = self.file_manager.get_current_file()
        current_file.set_anim_enabled(False)

        # Handle star toggle
        with self.widget_manager.get_blocked("star_toggle") as star_toggle:
            star_toggle.set_active(current_file.is_starred()) 

        with self.widget_manager.get_blocked("star_button") as star_button:
            star_button.set_active(current_file.is_starred()) 

        # Update main viewer and thumbnails
        missing_image = GTKIconImage(gtk.STOCK_MISSING_IMAGE, 128)
        self.image_viewer.load(current_file)
        self.fit_viewer(force=True) # Force immediate (and scaled) redraw
        self.th_left.load(missing_image)
        self.th_right.load(missing_image)
        self.loader_left.clear()
        self.loader_left.push((self.prepare_thumbnail, 
                              (self.th_left, self.file_manager.get_prev_file())))
        self.loader_right.clear()
        self.loader_right.push((self.prepare_thumbnail, 
                               (self.th_right, self.file_manager.get_next_file())))
        self.main_loader.clear()
        self.main_loader.push((self.preload_main_viewer, 
                               (self.image_viewer, current_file)))

        # Handle extract buttons
        self.widget_manager.get("extract_mitem").set_sensitive(current_file.can_be_extracted())
        self.widget_manager.get("extract_button").set_sensitive(current_file.can_be_extracted())

        # Handle reuse checkbox and button
        self.widget_manager.get("reuse_mitem").set_sensitive(bool(self.last_targets))
        self.widget_manager.get("reuse_button").set_sensitive(bool(self.last_targets))

        # Reset zoom toggle
        self.widget_manager.set_active("zoom_to_fit_toggle", True)
        self.widget_manager.set_active("zoom_to_fit_button", True)

        # Refresh the pinbar buckets
        self.pinbar.refresh_buckets()

        self.refresh_info()

    # This function will load the animated GIF in a separate thread:
    def preload_main_viewer(self, viewer, file_):
        anim_enabled = self.widget_manager.get("animation_toggle").get_active()
        file_.set_anim_enabled(anim_enabled)
        if anim_enabled:
            try:
                viewer.force_zoom(*viewer.get_size())
                file_.get_pixbuf_anim_at_size(*viewer.get_scaled_size())
                return (self.load_main_viewer, (viewer, file_))
            except:
                return (None, None)
        else:
            return (None, None)

    # This function will just reload the main viewer, after enabling
    # animation for the current file and having loaded the animated
    # pixbuf in the cache (so the loading operation doesn't block the 
    # main thread):
    def load_main_viewer(self, viewer, file_):
        self.fit_viewer(force=True)

    # This function will preload the thumbnail in a separate thread:
    def prepare_thumbnail(self, thumb, file_):
        file_.get_pixbuf() # it will be obtained and cached
        return (thumb.load, (file_,))

    def fit_viewer(self, force=False):
        allocation = self.scrolled.get_widget().allocation
        width, height = allocation.width, allocation.height
        # Only redraw if size changed:
        if (width, height) != self.image_viewer.get_size() or force:
            self.image_viewer.zoom_at_size(width, height)
            self.image_viewer.set_size(width, height)

    def refresh_info(self):
        self.refresh_title()
        self.refresh_filename()
        self.refresh_status()

    def refresh_title(self):
        image_file = self.file_manager.get_current_file()
        self.window.set_title(image_file.get_filename())

    def refresh_filename(self):
        image_file = self.file_manager.get_current_file()
        filename = cgi.escape(image_file.get_filename())
        markup = "<b><span foreground='white'>%s</span></b>" % filename
        self.file_name.set_markup(markup)

    def refresh_status(self):
        image_file = self.file_manager.get_current_file()

        # Markup reference:
        # http://www.gtk.org/api/2.6/pango/PangoMarkupFormat.html

        file_info  = "<i>Date:</i> %s | " % image_file.get_mtime()
        file_info += "<i>Dimensions:</i> %s pixels | " % image_file.get_dimensions()
        file_info += "<i>Size:</i> %s | " % image_file.get_filesize()
        file_info += "<i>Zoom:</i> %d%% | " % self.image_viewer.get_zoom_factor()
        file_info += "<i>Rotation:</i> %d degrees\n" % image_file.get_rotation()
        file_info += "<i>SHA1:</i> %s" % image_file.get_sha1()

        file_info += "\n<i>Base directory:</i> <b>%s</b>" % self.base_dir

        if self.last_targets:
            file_info += "\n<i>Last directory:</i> <b>%s</b>" % self.last_targets[0]

        if not self.undo_stack.empty():
            last_action = self.undo_stack.top()
            background, foreground = {
                Action.NORMAL : ("green", None),
                Action.WARNING : ("yellow", None),
                Action.DANGER : ("red", "white")
            }[last_action.severity]
            span = "<span"
            if background: span += " background='%s'" % background
            if foreground: span += " foreground='%s'" % foreground
            span += ">%s</span>" % last_action.description
            file_info += "\n<i>Last action:</i> " + span

        scanner = FileScanner()
        files = scanner.get_files_from_dir(image_file.get_dirname())

        inverse_order = self.widget_manager.get("inverted_order_toggle").active
        file_index = "<b><big>%d/%d</big></b> (%d)\n<i>Order:</i> %s %s" % \
                     (self.file_manager.get_current_index() + 1, 
                      self.file_manager.get_list_length(),
                      len(files),
                      self.files_order,
                      "Desc" if inverse_order else "Asc")

        rss, vsize = get_process_memory_usage()
        file_index += "\n<i>RSS:</i> %s\n<i>VSize:</i> %s" % (Size(rss), Size(vsize))

        self.file_info.set_markup(file_info)
        self.file_index.set_markup(file_index)
        self.file_index.set_justify(gtk.JUSTIFY_RIGHT)

    def reorder_files(self):
        inverse_order = self.widget_manager.get("inverted_order_toggle").active

        if self.files_order == "Date":
            self.file_manager.sort_by_date(inverse_order)
        elif self.files_order == "Name":
            self.file_manager.sort_by_name(inverse_order)
        elif self.files_order == "Size":
            self.file_manager.sort_by_size(inverse_order)
        elif self.files_order == "Dimensions":
            self.file_manager.sort_by_dimensions(inverse_order)
        else:
            assert(False)

    def handle_args(self, args):
        kw_args = {}
        for arg, func, key, default in args:
            dialog = TextEntryDialog(self.window, arg + ":", str(default))
            value = dialog.run()
            if value is None:
                return
            try:
                value = func(value)
            except Exception, e:
                ErrorDialog(self.window, "Error: " + str(e)).run()
                return
            kw_args[key] = value
        return kw_args

    def get_args(self, args):
        ret = []
        for text, func, default in args:
            dialog = TextEntryDialog(self.window, text + ":", str(default))
            value = dialog.run()
            if value is None:
                return
            try:
                ret.append(func(value))
            except Exception, e:
                ErrorDialog(self.window, "Error: " + str(e)).run()
                return
        return ret

    def execute_viewer(self, args):
        main_py = os.path.join(os.path.dirname(__file__), "main.py")
        execute([sys.executable, main_py] + args)

    def quit_app(self):
        gtk.Widget.destroy(self.window)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        bindings = {
            ## Generic actions:
            "Escape"      : self.quit_app,

            ## Image:
            "v"           : lambda: self.on_toggle_fullview(None),

            ## Files navigation:
            "Right"       : lambda: self.on_go_forward(None),
            "Left"        : lambda: self.on_go_back(None),
        }

        return bindings

    ## action handlers
    def on_quit_app(self, _):
        self.quit_app()

    def on_show_about(self, _):
        about = AboutDialog(self.window)
        about.show()

    def on_show_commands_reference(self, _):
        info = []

        root_path = os.path.split(os.path.dirname(__file__))[0]
        with open(os.path.join(root_path, "accelerators.txt")) as input_:
            for line in input_.readlines():
                info.append(map(string.strip, line.split(":")))

        dialog = TabbedInfoDialog(self.window, info)
        dialog.show()

    def on_toggle_fullscreen(self, toggle):
        if toggle.get_active():
            self.window.fullscreen()
        else:
            self.window.unfullscreen()

        self.widget_manager.set_active("fullscreen_toggle", toggle.get_active())
        self.widget_manager.set_active("fullscreen_button", toggle.get_active())

    def on_toggle_fullview(self, _):
        fullscreen_on = self.widget_manager.get("fullscreen_toggle").active
        toolbar_on = self.widget_manager.get("toolbar_toggle").active
        filterbar_on = self.widget_manager.get("filterbar_toggle").active
        pinbar_on = self.widget_manager.get("pinbar_toggle").active
        thumbnails_on = self.widget_manager.get("thumbnails_toggle").active
        status_bar_on = self.widget_manager.get("status_bar_toggle").active

        if not self.fullview_active:
            if not fullscreen_on:
                self.window.fullscreen()
            self.menu_bar.hide()
            self.toolbar.hide()
            self.filterbar.hide()
            self.pinbar.hide()
            self.go_back_icon.hide()
            self.go_forward_icon.hide()
            self.th_left.hide()
            self.th_right.hide()
            self.file_name.hide()
            self.status_bar.hide()
            self.fullview_active = True
        else:
            if not fullscreen_on:
                self.window.unfullscreen()
            self.menu_bar.show()
            if toolbar_on:
                self.toolbar.show()
            if filterbar_on:
                self.filterbar.show()
            if pinbar_on:
                self.pinbar.show()
            self.go_back_icon.show()
            self.go_forward_icon.show()
            if thumbnails_on:
                self.th_left.show()
                self.th_right.show()
            self.file_name.show()
            if status_bar_on:
                self.status_bar.show()
            self.fullview_active = False

    def on_toggle_toolbar(self, toggle):
        if toggle.active:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def on_toggle_thumbnails(self, toggle):
        if toggle.active:
            self.th_left.show()
            self.th_right.show()
        else:
            self.th_left.hide()
            self.th_right.hide()

    def on_toggle_status_bar(self, toggle):
        if toggle.active:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def on_show_filterbar(self, toggle):
        if toggle.active:
            self.filterbar.show()
            self.window.set_focus(self.widget_manager.get("filter_entry"))
        else:
            self.filterbar.hide()

    def on_show_pinbar(self, toggle):
        if toggle.active:
            self.pinbar.show()
        else:
            self.pinbar.hide()

    def on_goto_first(self, _):
        self.file_manager.go_first()

    def on_goto_last(self, _):
        self.file_manager.go_last()

    def on_jump_forward(self, _):
        self.file_manager.go_forward(10)

    def on_jump_back(self, _):
        self.file_manager.go_backward(10)

    def on_jump_to(self, _):
        dialog = TextEntryDialog(self.window, "Jump to:")
        value = dialog.run()
        if value is None:
            return
        try:
            value = int(value)-1
        except Exception, e:
            ErrorDialog(self.window, "Error: " + str(e)).run()
            return
        self.file_manager.go_to(value)

    def on_go_forward(self, _):
        self.file_manager.go_forward(1)

    def on_go_back(self, _):
        self.file_manager.go_backward(1)

    def get_base_dir(self):
        if self.base_dir:
            return self.base_dir
        else:
            return self.file_manager.get_current_file().get_dirname()

    def on_copy_to_target(self, _):
        selector = TargetSelectorDialog(parent=self.window,
                                        initial_dir=self.get_base_dir(), 
                                        last_targets=self.last_targets, 
                                        callback=self.on_copy_target_selected)
        selector.run()

    def on_move_to_target(self, _):
        selector = TargetSelectorDialog(parent=self.window,
                                        initial_dir=self.get_base_dir(), 
                                        last_targets=self.last_targets, 
                                        callback=self.on_target_selected)
        selector.run()

    def on_open_file(self, _):
        initial_dir = self.file_manager.get_current_file().get_dirname()
        open_dialog = OpenDialog(self.window, initial_dir, self.on_file_selected, self.on_dir_selected)
        open_dialog.run()

    def on_rename_current(self, _):
        filename = self.file_manager.get_current_file().get_filename()
        renamer = RenameDialog(self.window, filename, self.on_new_name_selected)
        renamer.run()

    def on_select_base_dir(self, _):
        selector = BasedirSelectorDialog(parent=self.window,
                                         initial_dir=self.get_base_dir(), 
                                         last_targets=self.last_targets, 
                                         callback=self.on_base_dir_selected)
        selector.run()

    def on_gallery_view(self, _):
        gallery = GalleryViewer(title="", 
                                parent=self.window, 
                                files=self.file_manager.get_files(),
                                callback=self.file_manager.go_file)
        gallery.run()

    def on_reuse_target(self, _):
        if not self.last_targets:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.move_current(self.last_targets[0])

    def on_undo(self, _):
        if self.undo_stack.empty():
            InfoDialog(self.window, "Nothing to undo!").run()
            return

        action = self.undo_stack.pop()
        action.undo()

    def on_toggle_star(self, _):
        self.undo_stack.push(self.file_manager.toggle_star())

    def on_delete_current(self, _):
        self.undo_stack.push(self.file_manager.delete_current())

    def on_mass_download(self, _):
        args = [("URL Pattern:", str, ""),
                ("First index", int, ""),
                ("Last index", int, "")]

        pattern, initial, final = self.get_args(args)

        if not initial <= final or initial < 1:
            ErrorDialog(self.window, "Invalid range: %d - %d" % (initial, final)).run()
            return

        mdownloader = MultiDownloader(pattern, initial, final)

        tmp_dir = tempfile.mkdtemp(suffix="gtk-viewer")
        dialog = ProgressBarDialog(self.window, "Downloading files...")
        dialog.show()
        updater = Updater(mdownloader.run(tmp_dir),
                          dialog.update,
                          self.on_mass_download_finished,
                          (tmp_dir, dialog,))
        updater.start()

    def on_mass_download_finished(self, tmp_dir, dialog):
        try:
            dialog.destroy()
            # Run a separate instance of the viewer on this dir:
            self.execute_viewer([tmp_dir])
        finally:
            shutil.rmtree(tmp_dir)

    def on_mass_delete(self, _):
        current, total = (self.file_manager.get_current_index() + 1, 
                          self.file_manager.get_list_length())

        args = [("First file to delete (current: %d)" % current, int, 1),
                ("Last file to delete (current: %d)" % current, int, total)]

        initial, final = self.get_args(args)

        if not initial <= final or initial < 1 or final > total:
            ErrorDialog(self.window, "Invalid range: %d - %d" % (initial, final)).run()
            return

        dialog = QuestionDialog(self.window,
                                "Are you sure you want to delete from %d to %d?" \
                                 % (initial, final))

        if not dialog.run():
            return

        dialog = ProgressBarDialog(self.window, "Deleting files...")
        dialog.show()
        updater = Updater(self.file_manager.mass_delete(initial - 1, final - 1),
                          dialog.update,
                          lambda dialog: dialog.destroy(),
                          (dialog,))
        updater.start()

    def on_open_in_nautilus(self, widget):
        current_file = self.file_manager.get_current_file()
        execute(["nautilus", current_file.get_filename()])

    def on_sort_by_date(self, widget):
        self.files_order = "Date"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_date_toggle", True),
                                  ("sort_by_date_button", True),
                                  ("sort_by_size_toggle", False),
                                  ("sort_by_size_button", False),
                                  ("sort_by_dimensions_toggle", False),
                                  ("sort_by_name_toggle", False),
                                  ("sort_by_name_button", False)]:
            self.widget_manager.set_active(widget_id, active)

        self.reorder_files()

    def on_sort_by_name(self, widget):
        self.files_order = "Name"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_name_toggle", True),
                                  ("sort_by_name_button", True),
                                  ("sort_by_size_toggle", False),
                                  ("sort_by_size_button", False),
                                  ("sort_by_dimensions_toggle", False),
                                  ("sort_by_date_toggle", False),
                                  ("sort_by_date_button", False)]:
            self.widget_manager.set_active(widget_id, active)

        self.reorder_files()

    def on_sort_by_size(self, widget):
        self.files_order = "Size"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_name_toggle", False),
                                  ("sort_by_name_button", False),
                                  ("sort_by_size_toggle", True),
                                  ("sort_by_size_button", True),
                                  ("sort_by_dimensions_toggle", False),
                                  ("sort_by_date_toggle", False),
                                  ("sort_by_date_button", False)]:
            self.widget_manager.set_active(widget_id, active)

        self.reorder_files()

    def on_sort_by_dimensions(self, widget):
        self.files_order = "Dimensions"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_name_toggle", False),
                                  ("sort_by_name_button", False),
                                  ("sort_by_size_toggle", False),
                                  ("sort_by_size_button", False),
                                  ("sort_by_dimensions_toggle", True),
                                  ("sort_by_date_toggle", False),
                                  ("sort_by_date_button", False)]:
            self.widget_manager.set_active(widget_id, active)

        self.reorder_files()

    def on_toggle_sort_order(self, widget):
        if not self.files_order:
            return

        inverted_order_toggle = self.widget_manager.get("inverted_order_toggle")
        inverted_order_button = self.widget_manager.get("inverted_order_button")

        if widget is inverted_order_button:
            inverted_order_toggle.set_active(not inverted_order_toggle.get_active())

        if inverted_order_toggle.get_active():
            inverted_order_button.set_stock_id("sort-descending")
        else:
            inverted_order_button.set_stock_id("sort-ascending")

        self.reorder_files()

    def on_filetype_toggle(self, widget):
        for filetype in self.filter_.get_valid_filetypes():
            button_id = "filter_%s_button" % filetype
            toggle_id = "filter_%s_toggle" % filetype
            if widget is self.widget_manager.get(toggle_id):
                self.widget_manager.set_active(button_id, widget.get_active())
                break
            if widget is self.widget_manager.get(button_id):
                self.widget_manager.set_active(toggle_id, widget.get_active())
                break

        # update the filter to match the toggle state:
        self.filter_.enable_filetype(filetype, widget.get_active())
        self.apply_filter()

    def on_status_toggle(self, widget):
        for status in self.filter_.get_valid_status():
            button_id = "filter_%s_button" % status
            toggle_id = "filter_%s_toggle" % status
            if widget is self.widget_manager.get(toggle_id):
                self.widget_manager.set_active(button_id, widget.get_active())
                break
            if widget is self.widget_manager.get(button_id):
                self.widget_manager.set_active(toggle_id, widget.get_active())
                break

        # update the filter to match the toggle state:
        self.filter_.enable_status(status, widget.get_active())
        self.apply_filter()

    def on_show_all_filetypes(self, _):
        self.toggle_all_filetypes(True)
        self.apply_filter()

    def on_hide_all_filetypes(self, _):
        self.toggle_all_filetypes(False)
        self.apply_filter()

    def on_show_all_status(self, _):
        self.toggle_all_status(True)
        self.apply_filter()

    def on_hide_all_status(self, _):
        self.toggle_all_status(False)
        self.apply_filter()

    def on_filter_entry_focus_in(self, widget, _):
        self.window.remove_accel_group(self.accel_group)

    def on_filter_entry_focus_out(self, widget, _):
        self.window.add_accel_group(self.accel_group)

    def on_filter_entry_activate(self, entry):
        self.window.set_focus(None)
        self.filter_.enable_pattern(entry.get_text())
        self.apply_filter()

    def on_filter_entry_clear(self, _):
        self.widget_manager.get("filter_entry").set_text("")
        self.filter_.enable_pattern("")
        self.apply_filter()

    def on_show_info(self, _):
        current_file = self.file_manager.get_current_file()
        metadata = current_file.get_metadata()

        if not metadata:
            ErrorDialog(self.window, "Error: No information available").run()
            return

        dialog = TabbedInfoDialog(self.window, metadata)
        dialog.show()

    def on_external_open(self, _):
        current_file = self.file_manager.get_current_file()
        current_file.external_open()

    def on_extract_contents(self, _):
        current_file = self.file_manager.get_current_file()

        # Get special args:
        kw_args = self.handle_args(current_file.get_extract_args())

        # Create a temporary dir to hold the contents:
        tmp_dir = tempfile.mkdtemp(suffix="gtk-viewer")
        dialog = ProgressBarDialog(self.window, "Extracting contents...")
        dialog.show()
        updater = Updater(current_file.extract_contents(tmp_dir, **kw_args),
                          dialog.update,
                          self.on_extraction_finished,
                          (tmp_dir, dialog))
        updater.start()

    def on_extraction_finished(self, tmp_dir, dialog):
        try:
            dialog.destroy()
            # Run a separate instance of the viewer on this dir:
            self.execute_viewer(["-r", tmp_dir])
        finally:
            shutil.rmtree(tmp_dir)

    def on_generate_gif(self, _):
        generator = GIFGenerator()
        dialog = OutputDialog(self.window, 
                              lambda filename: self.on_generate_file(generator, 
                                                                     filename))
        dialog.run()

    def on_generate_archive(self, _):
        generator = ArchiveGenerator()
        dialog = OutputDialog(self.window, 
                              lambda filename: self.on_generate_file(generator, 
                                                                     filename))
        dialog.run()

    def on_generate_pdf(self, _):
        generator = PDFGenerator()
        dialog = OutputDialog(self.window, 
                              lambda filename: self.on_generate_file(generator, 
                                                                     filename))
        dialog.run()

    def on_generate_file(self, generator, output):
        kw_args = self.handle_args(generator.get_args())

        files = map(lambda f: f.get_filename(),
                    self.file_manager.get_files())

        dialog = ProgressBarDialog(self.window, "Generating file...")
        dialog.show()
        updater = Updater(generator.generate(files, output, **kw_args),
                          dialog.update,
                          self.on_generation_finished,
                          (output, dialog))
        updater.start()

    def on_generation_finished(self, output, dialog):
        dialog.destroy()
        # Open the output file in a separate instance of the viewer:
        self.execute_viewer([output])

    def on_enable_animation(self, toggle):
        self.widget_manager.set_active("animation_toggle", toggle.get_active())
        self.widget_manager.set_active("animation_button", toggle.get_active())
        self.reload_viewer()

    def on_toggle_zoom(self, toggle):
        if toggle.get_active():
            self.fit_viewer(force=True)
        else:
            self.image_viewer.zoom_at(100)

        self.widget_manager.set_active("zoom_to_fit_toggle", toggle.get_active())
        self.widget_manager.set_active("zoom_to_fit_button", toggle.get_active())

        self.refresh_info()

    def on_zoom_in(self, _):
        self.widget_manager.set_active("zoom_to_fit_toggle", False)
        self.widget_manager.set_active("zoom_to_fit_button", False)
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 1.05)
        self.refresh_info()

    def on_zoom_out(self, _):
        self.widget_manager.set_active("zoom_to_fit_toggle", False)
        self.widget_manager.set_active("zoom_to_fit_button", False)
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 0.95)
        self.refresh_info()

    def on_rotate_c(self, _):
        self.image_viewer.rotate_c()
        self.reload_viewer()

    def on_rotate_cc(self, _):
        self.image_viewer.rotate_cc()
        self.reload_viewer()

    def on_flip_horizontal(self, _):
        self.image_viewer.flip_horizontal()

    def on_flip_vertical(self, _):
        self.image_viewer.flip_vertical()

    ##

    def run(self):
        gtk.main()

