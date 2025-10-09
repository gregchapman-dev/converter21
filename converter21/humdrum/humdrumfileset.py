# ------------------------------------------------------------------------------
# Name:          HumdrumFileSet.py
# Purpose:       Manage a list of HumdrumFile objects.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from pathlib import Path

import music21 as m21

from converter21 import M21Utilities
from converter21.humdrum import HumdrumFileStream
from converter21.humdrum import HumdrumFile

class HumdrumFileSet:
    def __init__(
        self,
        fileName: str | Path | None = None,
        acceptSyntaxErrors: bool = False,
        verovioCompatibleImport: bool = False
    ) -> None:
        M21Utilities.adjustMusic21Behavior()
        self.humdrumFiles: list[HumdrumFile] = []
        self.acceptSyntaxErrors = acceptSyntaxErrors
        self.verovioCompatibleImport = verovioCompatibleImport
        if fileName is not None:
            self.readFile(fileName)

    def readFile(self, fileName: str | Path) -> int:
        self.humdrumFiles = []
        self.readAppendFile(fileName)
        return len(self)

    def readString(self, contents: str) -> int:
        self.humdrumFiles = []
        self.readAppendString(contents)
        return len(self)

    def readAppendString(self, contents: str) -> int:
        hfStream = HumdrumFileStream(contents)
        self.readAppendStream(hfStream)
        return len(self)

    def readAppendFile(self, fileName: str | Path) -> int:
        contents: str = ''
        try:
            with open(fileName, encoding='utf-8') as f:
                contents = f.read()
        except UnicodeDecodeError:
            with open(fileName, encoding='latin-1') as f:
                contents = f.read()
        self.readAppendString(contents)
        return len(self)

    def readAppendStream(self, hfStream: HumdrumFileStream) -> int:
        hf: HumdrumFile = HumdrumFile(
            acceptSyntaxErrors=self.acceptSyntaxErrors,
            verovioCompatibleImport=self.verovioCompatibleImport
        )
        while hfStream.read(hf):
            self.humdrumFiles.append(hf)
            hf = HumdrumFile(
                acceptSyntaxErrors=self.acceptSyntaxErrors,
                verovioCompatibleImport=self.verovioCompatibleImport
            )
        return len(self)

    def createMusic21Stream(self, number: int | None = None) -> m21.stream.Opus | m21.stream.Score:
        # if there is only one Score (the usual case), we don't wrap it in an Opus.

        if number is not None:
            theRightHF: HumdrumFile | None = None
            # search for '!!!ONM: 3' or somesuch
            for hf in self.humdrumFiles:
                onmValue: str = hf.getGlobalReferenceValueForKey('ONM')
                try:
                    if int(onmValue) == number:
                        theRightHF = hf
                        break
                except Exception:
                    pass
            if theRightHF is None:
                return m21.stream.Score()
            return theRightHF.createMusic21Stream()

        # OK, there is no number requested, return all the humdrumfiles.
        scores: list[m21.stream.Score] = []
        for hf in self.humdrumFiles:
            scores.append(hf.createMusic21Stream())

        if not scores:
            return m21.stream.Score()

        if len(scores) == 1:
            # here we remove any number=1 metadata because it's the
            # only score, so score # 1 in the file is meaningless.
            md: m21.metadata.Metadata | None = scores[0].metadata
            if md is not None:
                nums: tuple[m21.metadata.Text, ...] = md['number']
                if len(nums) == 1 and str(nums[0]) == '1':
                    md['number'] = None

            return scores[0]

        opusNumSyntaxErrorsFixed: int = 0
        opus = m21.stream.Opus()
        for score in scores:
            opus.append(score)
            if hasattr(score, 'c21_syntax_errors_fixed'):
                opusNumSyntaxErrorsFixed += getattr(score, 'c21_syntax_errors_fixed')
        opus.c21_syntax_errors_fixed = opusNumSyntaxErrorsFixed  # type: ignore
        return opus

    def __len__(self) -> int:
        # number of HumdrumFiles in HumdrumFileSet
        return len(self.humdrumFiles)

    def __getitem__(self, index: int | slice) -> HumdrumFile | list[HumdrumFile] | None:
        if not isinstance(index, int):
            # if its a slice, out-of-range start/stop won't crash
            return self.humdrumFiles[index]

        if index < 0:
            index += len(self.humdrumFiles)

        if index < 0:
            return None
        if index >= len(self.humdrumFiles):
            return None

        return self.humdrumFiles[index]
