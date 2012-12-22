import os
import glob

import gtk

from videofile import VideoFile
from giffile import GIFFile
from pdffile import PDFFile
from epubfile import EPUBFile

class FileTypeFilter:
    allowed_extensions = []

    @classmethod
    def get_valid_extensions(cls):
        return { "videos" : VideoFile.valid_extensions,
                 "images" : cls.get_image_extensions(),
                 "gifs" : GIFFile.valid_extensions,
                 "pdfs" : PDFFile.valid_extensions,
                 "epubs" : EPUBFile.valid_extensions }

    @classmethod
    def get_image_extensions(cls):
        ret = []

        for format_ in gtk.gdk.pixbuf_get_formats():
            for extension in format_["extensions"]:
                if extension != "gif":
                    ret.append(extension)

        return ret

    @classmethod
    def process_options(cls, options):
        valid_extensions = cls.get_valid_extensions()

        for option in dir(options):
            if (option.startswith("allow_") and
                getattr(options, option)):
                kind = option.replace("allow_", "")
                cls.allowed_extensions += valid_extensions[kind]

        if not cls.allowed_extensions:
            for kind, extensions in valid_extensions.iteritems():
                cls.allowed_extensions += extensions

    @classmethod
    def has_allowed_ext(cls, filename):
        for extension in cls.allowed_extensions:
            if ("." + extension) in filename.lower():
                return True

        return False

def get_files_from_dir(directory):
    files = []

    for filename in glob.glob(os.path.join(directory, "*")):
        if FileTypeFilter.has_allowed_ext(filename):
            files.append(filename)

    return sorted(files)

def get_files_from_args(args):
    files = []
    start_file = None

    if len(args) == 1: 
        if os.path.isdir(args[0]):
            files = get_files_from_dir(args[0])
        else:
            if FileTypeFilter.has_allowed_ext(args[0]):
                start_file = args[0]
            files = get_files_from_dir(os.path.dirname(args[0]))
    else:
        for arg in args:
            if os.path.isdir(arg):
                files.extend(get_files_from_dir(arg))
            elif FileTypeFilter.has_allowed_ext(arg):
                files.append(arg)

    return files, start_file

def get_files_from_args_recursive(args):
    files = []
    start_file = None

    for arg in args:
        for dirpath, dirnames, filenames in os.walk(arg):
            files.extend(get_files_from_dir(dirpath))

    return files, start_file

