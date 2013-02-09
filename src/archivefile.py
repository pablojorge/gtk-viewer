import os
import pexpect

import gtk

from imagefile import ImageFile
from cache import cached
from system import execute

class ArchiveFile(ImageFile):
    description = "archive"
    valid_extensions = ["zip", "rar"]

    def __init__(self, filename):
        ImageFile.__init__(self, filename)
        self.delegate = self.build_delegate(filename)

    @classmethod
    def build_delegate(cls, filename):
        if filename.endswith("zip"):
            return ZIPFile(filename)
        elif filename.endswith("rar"):
            return RARFile(filename)
        else:
            return None

    @cached()
    def get_pixbuf(self):
        root_path = os.path.split(os.path.dirname(__file__))[0]
        pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(root_path, "icons/archive.png"))
        return pixbuf

    #def get_sha1(self):
    #    return ""

    def extract_contents(self, tmp_dir):
        return self.delegate.extract_contents(tmp_dir)

    def can_be_extracted(self):
        return True

class ZIPFile:
    def __init__(self, filename):
        self.filename = filename

    #@cached()
    #def get_metadata(self):
    #    ret = []
    #    output = execute(["unzip", "-l", self.get_filename()], check_retcode=False)
    #    lines = output.split("\n")
    #    for index, line in enumerate(lines):
    #        tokens = filter(lambda x: x, line.split(" "))
    #    return 0

    def extract_contents(self, tmp_dir):
        try:
            child = pexpect.spawn("unzip", [self.filename, "-d", tmp_dir])
            while True:
                try:
                    child.expect("inflating")
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

class RARFile:
    def __init__(self, filename):
        self.filename = filename

    def extract_contents(self, tmp_dir):
        cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            child = pexpect.spawn("unrar", ["x", self.filename])
            while True:
                try:
                    child.expect("Extracting")
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e
        finally:
            os.chdir(cwd)

