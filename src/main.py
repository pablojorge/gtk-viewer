import os
import optparse

from collections import defaultdict

from filefactory import FileFactory
from filescanner import FiletypeFilter, FileScanner
from viewerapp import ViewerApp

# XXX Starting zoom level when zooming in/out
# XXX Icons can't be found if program is ran outside source dir
# TODO Filter for starred files

# TODO Asynchronous loading of images
# TODO Support for copying files
# TODO Show images metadata
# TODO Integrate metadata manipulation for MP3s/PDFs/EPubs (show, edit, autogen)
# TODO Undo pane
# TODO Fix accelerators handled manually with key bindings (Left, Right, Esc, V)
# TODO Thumbnail view (complete, as a bar or both)
# TODO Support for delete / undelete in Mac OS X

def check_directories(args):
    for arg in args:
        for dirpath, dirnames, filenames in os.walk(arg):
            if dirnames and filenames:
                print "'%s': dirs and files mixed (%d files)" % \
                      (dirpath, len(filenames))
            elif not dirnames and not filenames:
                print "'%s': empty" % (dirpath)

def print_stats(files):
    files = map(FileFactory.create, files)
    counter = defaultdict(lambda:0)

    for file in files:
        counter[file.description] += 1

    for type in counter:
        print "'%s': %d files" % (type, counter[type])

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] FILE...")

    parser.add_option("-r", "--recursive", action="store_true", default=False)
    parser.add_option("-c", "--check", action="store_true", default=False)
    parser.add_option("-s", "--stats", action="store_true", default=False)
    parser.add_option("", "--base-dir")

    parser.add_option("", "--allow-images", action="store_true", default=False)
    parser.add_option("", "--allow-gifs", action="store_true", default=False)
    parser.add_option("", "--allow-pdfs", action="store_true", default=False)
    parser.add_option("", "--allow-epubs", action="store_true", default=False)
    parser.add_option("", "--allow-videos", action="store_true", default=False)

    options, args = parser.parse_args()

    if not args:
        args = ["."]

    if options.check:
        check_directories(args)
        return

    filter_ = FiletypeFilter()
    filter_.set_from_options(options)

    scanner = FileScanner(filter_, options.recursive)
    files, start_file = scanner.get_files_from_args(args)

    if options.stats:
        print_stats(files)
        return

    try:
        app = ViewerApp(files, start_file, options.base_dir)
        app.run()
    except Exception, e:
        import traceback
        traceback.print_exc()
        print "Error:", e

if __name__ == "__main__":
    main()
