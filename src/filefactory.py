from imagefile import ImageFile
from pdffile import PDFFile
from epubfile import EPUBFile
from videofile import VideoFile
from giffile import GIFFile
from archivefile import ArchiveFile

class FileFactory:
    def __init__(self):
        pass

    @classmethod
    def create(cls, filename):
        for cls in PDFFile, EPUBFile, VideoFile, GIFFile, ArchiveFile:
            for ext in cls.valid_extensions:
                if filename.lower().endswith("." + ext):
                    return cls(filename)

        return ImageFile(filename)

