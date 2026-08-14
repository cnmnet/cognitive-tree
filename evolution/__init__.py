"""Evolution layer: staging pool, fast/slow loops and patch operators."""

from .godel import GödelAgent
from .meta_layer import MetaLayer
from .fast_loop import FastLoop
from .governance import auditor, debate_on_config, proposal
from .operators import graft, merge, promote, prune
from .slow_loop import SlowLoop
from .staging_pool import StagingPool

__all__ = [
    "FastLoop",
    "GödelAgent",
    "MetaLayer",
    "SlowLoop",
    "StagingPool",
    "auditor",
    "debate_on_config",
    "graft",
    "merge",
    "promote",
    "proposal",
    "prune",
]
