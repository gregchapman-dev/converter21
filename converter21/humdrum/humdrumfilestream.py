# ------------------------------------------------------------------------------
# Name:          HumdrumFileStream.py
# Purpose:       Parses a string containing multiple scores/HumdrumFiles.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import re

from converter21.humdrum import HumdrumFile

class HumdrumFileStream:
    def __init__(
        self,
        datastring: str
    ) -> None:
        self.lines: list[str] = datastring.split('\n')
        self.currLine = 0
        self.newFileBuffer: str = ''
        self.universals: list[str] = []

    def readLine(self) -> str:
        theLine: str = self.lines[self.currLine]
        self.currLine += 1
        return theLine

    def eof(self) -> bool:
        return self.currLine >= len(self.lines)

    '''
    //////////////////////////////
    //
    // HumdrumFileStream::getFile -- fills a HumdrumFile class with content
    //    from the input stream or next input file in the list.  Returns
    //    true if content was extracted, fails if there is no more HumdrumFiles
    //    in the input stream.
    Currently only fills from contents string (self.lines).
    '''
    def read(self, infile: HumdrumFile) -> bool:
        # Read from self.lines into the next HumdrumFile.
        buffer: str = ''
        if self.newFileBuffer:
            buffer = self.newFileBuffer + '\n'
        self.newFileBuffer = ''


        # If there is newFileBuffer content, then set the filename
        # of the HumdrumFile to that value.
        if self.newFileBuffer:
            m = re.search(
                r'(^!!!!SEGMENT\s*([+-]?\d+)?\s*:\s*(.*)\s*$)',
                self.newFileBuffer
            )
            if m:
                if m.group(1):
                    infile.segmentLevel = int(m.group(1))
                else:
                    infile.segmentLevel = 0
                if m.group(2):
                    infile.fileName = m.group(2)

        # Start reading the input stream.  If !!!!SEGMENT: universal comment
        # is found, then store that line in self.newFileBuffer and return the
        # newly read HumdrumFile.  If other universal comments are found, then
        # overwrite the old universal comments here.

        foundUniversal: bool = False
        dataFound: bool = False
        starstarFound: bool = False

        if self.eof():
            # no lines to read
            return False

        if self.newFileBuffer.startswith('**'):
            buffer += self.newFileBuffer + '\n'
            self.newFileBuffer = ''
            starstarFound = True

        while not self.eof():
            templine: str = self.readLine()
            if templine.startswith('!!!!SEGMENT'):
                if buffer:
                    self.newFileBuffer = templine
                    break

            if templine.startswith('**'):
                if starstarFound:
                    self.newFileBuffer = templine
                    # already found a **, so this one is defined as a file
                    # segment.  Exit from the loop and process the previous
                    # content, waiting until the next read to start with
                    # this line.
                    break
                starstarFound = True

            if self.eof() and not templine:
                # No more data coming from current stream, so this is
                # the end of the HumdrumFile.  Break from the while loop
                # and then store the read contents of the stream in the
                # HumdrumFile.
                break

            if (len(templine) > 4
                    and templine.startswith('!!!!')
                    and templine[4] != '!'
                    and not dataFound
                    and not templine.startswith('!!!!filter:')
                    and not templine.startswith('!!!!SEGMENT:')):
                # This is a universal comment.  Should it be appended
                # to the list or should the current list be erased and
                # this record placed into the first entry?
                if foundUniversal:
                    # already found a previous universal, so append.
                    self.universals.append(templine)
                else:
                    # new universal comment, so delete all previous
                    # universal comments and store this one.
                    self.universals = [templine]
                    foundUniversal = True
                continue

            dataFound = True  # found something other than universal comments

            # store the data line for later parsing into HumdrumFile record:
            buffer += templine + '\n'

        # Arriving here means that reading of the data stream is complete.
        # The string stream variable "buffer" contains the HumdrumFile
        # content, so send it to the HumdrumFile variable.  Also, prepend
        # Universal comments (demoted into Global comments) at the start
        # of the data stream (maybe allow for postpending Universal comments
        # in the future).
        contents: str = ''

        for universal in self.universals:
            if universal.startswith('!!!!filter:'):
                continue
            contents += universal[1:] + '\n'

        contents += buffer

        oldFileName: str = infile.fileName
        infile.readStringNoRhythm(contents)

        newFileName: str = infile.fileName
        if not newFileName and oldFileName:
            infile.fileName = oldFileName

        infile.setFileNameFromSegment()

        return True
