# ------------------------------------------------------------------------------
# Name:          debugutilities.py
# Purpose:       Various debug utilities, such as DebugTreeBuilder.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

from xml.etree.ElementTree import TreeBuilder, Element

class DebugError(Exception):
    pass

class DebugTreeBuilder:
    def __init__(
        self,
        element_factory=None,
        *,
        comment_factory=None,
        pi_factory=None,
        insert_comments=False,
        insert_pis=False
    ) -> None:
        self.tb: TreeBuilder = TreeBuilder(
            element_factory=element_factory,
            comment_factory=comment_factory,
            pi_factory=pi_factory,
            insert_comments=insert_comments,
            insert_pis=insert_pis
        )
        self.stack: list[str] = []

    def start(self, name: str, attr: dict[str, str]):
        self.stack.append(name)
        self.tb.start(name, attr)

    def end(self, name: str):
        if self.stack[-1] != name:
            raise DebugError(
                f'mismatched tb.end call: is "{name}", should be "{self.stack[-1]}"'
            )
        self.tb.end(name)
        self.stack = self.stack[:-1]

    def data(self, theData: str):
        self.tb.data(theData)

    def close(self) -> Element:
        return self.tb.close()

