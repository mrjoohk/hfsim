from hf_sim.env import HFSimEnv, WorldModelEnvWrapper
from hf_sim.dataset import SequenceBuffer, collect_episodes
from world_model.rssm import RSSMWorldModel, RSSMConfig
import torch

env = HFSimEnv(curriculum_level=3, max_steps=500)
buf = SequenceBuffer(capacity=50_000)
wrapped = WorldModelEnvWrapper(env, buf)       # 자동 수집

collect_episodes(wrapped, env.action_space.sample, n_episodes=100, buffer=buf)

wm = RSSMWorldModel(RSSMConfig())
for _ in range(1000):
    obs, act, rew, cont = buf.sample_sequences(32, 50)
    out = wm.train_step(*[torch.from_numpy(x) for x in [obs, act, rew, cont]])
    print(f"loss={out.loss.item():.4f}")
