import os
import glob

import gtk

from videofile import VideoFile
from giffile import GIFFile
from pdffile import PDFFile
from epubfile import EPUBFile

from cache import Cache, cached

class FileFilter:
    STARRED   = "starred"
    UNSTARRED = "unstarred"

    def __init__(self):
        self.allowed_filetypes = set(FileFilter.get_valid_filetypes())
        self.allowed_status = set(FileFilter.get_valid_status())

    def is_filetype_enabled(self, filetype):
        return filetype in self.allowed_filetypes

    def is_status_enabled(self, status):
        return status in self.allowed_status

    def enable_filetype(self, filetype, enable):
        if enable:
            self.allowed_filetypes.add(filetype)
        elif not enable and self.is_filetype_enabled(filetype):
            self.allowed_filetypes.remove(filetype)

    def enable_status(self, status, enable):
        if enable:
            self.allowed_status.add(status)
        elif not enable and self.is_status_enabled(status):
            self.allowed_status.remove(status)

    @classmethod
    def get_valid_extensions(cls):
        return { "images" : cls.get_image_extensions(),
                 "videos" : VideoFile.valid_extensions,
                 "gifs" : GIFFile.valid_extensions,
                 "pdfs" : PDFFile.valid_extensions,
                 "epubs" : EPUBFile.valid_extensions }

    @classmethod
    def get_valid_filetypes(cls):
        return cls.get_valid_extensions().keys()

    @classmethod
    def get_valid_status(cls):
        return [cls.STARRED, cls.UNSTARRED]

    @classmethod
    def get_image_extensions(cls):
        ret = []

        for format_ in gtk.gdk.pixbuf_get_formats():
            for extension in format_["extensions"]:
                if extension != "gif":
                    ret.append(extension)

        return ret

    def has_allowed_ext(self, filename):
        valid_extensions = self.get_valid_extensions()

        for filetype in self.allowed_filetypes:
            for extension in valid_extensions[filetype]:
                if ("." + extension) in filename.lower():
                    return True

        return False

    def has_allowed_status(self, file_):
        if (self.STARRED in self.allowed_status and 
            file_.is_starred()):
            return True

        if (self.UNSTARRED in self.allowed_status and 
            not file_.is_starred()):
            return True

        return False

    def allowed(self, file_):
        return (self.has_allowed_ext(file_.get_filename()) and 
                self.has_allowed_status(file_))

class FileScanner:
    cache = Cache(shared=True)

    def __init__(self, filter_ = None, recursive = False):
        if filter_:
            self.filter_ = filter_
        else:
            self.filter_ = FileFilter()
        self.recursive = recursive

    @cached(cache)
    def get_dirs_from_dir(self, directory):
        dirs = []

        for entry in glob.glob(os.path.join(directory, "*")):
            if os.path.isdir(entry):
                dirs.append(entry)

        return sorted(dirs)
                
    @cached(cache)
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

