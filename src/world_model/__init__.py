"""World model backends for HF_Sim.

Provides a common WorldModelBackend protocol so that RSSM and DreamerV3
can be used interchangeably in training loops.

Usage:
    from world_model.rssm import RSSMWorldModel, RSSMConfig
    wm = RSSMWorldModel(RSSMConfig())

    # or for DreamerV3:
    from world_model.dreamer_v3 import DreamerV3Adapter
    wm = DreamerV3Adapter(...)
"""

from world_model.base import WorldModelBackend, WorldModelOutput

__all__ = ["WorldModelBackend", "WorldModelOutput"]
