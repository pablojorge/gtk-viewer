import os
import glob

import gtk

from videofile import VideoFile
from giffile import GIFFile
from pdffile import PDFFile
from epubfile import EPUBFile

class FiletypeFilter:
    def __init__(self):
        self.allowed_filetypes = set()

    def is_enabled(self, filetype):
        return filetype in self.allowed_filetypes

    def enable_filetype(self, filetype, enable):
        if enable:
            self.allowed_filetypes.add(filetype)
        elif not enable and self.is_enabled(filetype):
            self.allowed_filetypes.remove(filetype)

    def enable_all(self):
        for filetype in self.get_valid_filetypes():
            self.enable_filetype(filetype, True)

    def disable_all(self):
        self.allowed_filetypes.clear()

    def get_valid_extensions(self):
        return { "images" : self.get_image_extensions(),
                 "videos" : VideoFile.valid_extensions,
                 "gifs" : GIFFile.valid_extensions,
                 "pdfs" : PDFFile.valid_extensions,
                 "epubs" : EPUBFile.valid_extensions }

    def get_valid_filetypes(self):
        return self.get_valid_extensions().keys()

    def get_image_extensions(self):
        ret = []

        for format_ in gtk.gdk.pixbuf_get_formats():
            for extension in format_["extensions"]:
                if extension != "gif":
                    ret.append(extension)

        return ret

    def set_from_options(self, options):
        for option in dir(options):
            if (option.startswith("allow_") and
                getattr(options, option)):
                filetype = option.replace("allow_", "")
                self.enable_filetype(filetype, True)

        if not self.allowed_filetypes:
            self.enable_all()

    def has_allowed_ext(self, filename):
        valid_extensions = self.get_valid_extensions()

        for filetype in self.allowed_filetypes:
            for extension in valid_extensions[filetype]:
                if ("." + extension) in filename.lower():
                    return True

        return False

    def allowed(self, file_):
        return self.has_allowed_ext(file_.get_filename())

class FileScanner:
    def __init__(self, filter_, recursive = False):
        self.filter_ = filter_
        self.recursive = recursive

    def get_files_from_dir(self, directory):
        files = []

        for filename in glob.glob(os.path.join(directory, "*")):
            if self.filter_.has_allowed_ext(filename):
                files.append(filename)

        return sorted(files)

    def get_files_from_filename(self, filename):
        return self.get_files_from_dir(os.path.dirname(filename))

    def get_files_from_args(self, args):
        files = []
        start_file = None

        if self.recursive:
            for arg in args:
                for dirpath, dirnames, filenames in os.walk(arg):
                    files.extend(self.get_files_from_dir(dirpath))
        elif len(args) == 1: 
            if os.path.isdir(args[0]):
                files = self.get_files_from_dir(args[0])
            else:
                if self.filter_.has_allowed_ext(args[0]):
                    start_file = args[0]
                files = self.get_files_from_filename(args[0])
        else:
            for arg in args:
                if os.path.isdir(arg):
                    files.extend(self.get_files_from_dir(arg))
                elif self.filter_.has_allowed_ext(arg):
                    files.append(arg)

        return files, start_file

