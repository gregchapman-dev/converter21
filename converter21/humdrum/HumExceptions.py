class HumdrumSyntaxError(Exception):
    # poorly formed humdrum input
    pass

class HumdrumInternalError(Exception):
    # unexpected state during import or export
    pass

class HumdrumExportError(Exception):
    # error converting something to humdrum
    pass
