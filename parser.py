class AnalysisResult:

    def __init__(self):
        self.bestmove = None
        self.depth = 0
        self.cp = None
        self.mate = None
        self.pv = []
        self.nodes = None
        self.nps = None
        self.time = None

    def to_dict(self):

        return {
            "bestmove": self.bestmove,
            "depth": self.depth,
            "cp": self.cp,
            "mate": self.mate,
            "pv": self.pv,
            "nodes": self.nodes,
            "nps": self.nps,
            "time_ms": self.time,
        }